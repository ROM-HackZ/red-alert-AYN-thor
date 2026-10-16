#include "soscomp.h"
#include <stdint.h>
#include <string.h>
#include <assert.h>

// index table for stepping into step table.
static const short wCODECIndexTab[16] = {-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8};

static const short wCODECStepTab[89] = {
    7,    8,     9,     10,    11,    12,    13,    14,    16,    17,    19,    21,    23,    25,   28,
    31,   34,    37,    41,    45,    50,    55,    60,    66,    73,    80,    88,    97,    107,  118,
    130,  143,   157,   173,   190,   209,   230,   253,   279,   307,   337,   371,   408,   449,  494,
    544,  598,   658,   724,   796,   876,   963,   1060,  1166,  1282,  1411,  1552,  1707,  1878, 2066,
    2272, 2499,  2749,  3024,  3327,  3660,  4026,  4428,  4871,  5358,  5894,  6484,  7132,  7845, 8630,
    9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767};

#ifndef clamp
#define clamp(x, low, high) (((x) > (high)) ? (high) : (((x) < (low)) ? (low) : (x)))
#endif

void sosCODECInitStream(_SOS_COMPRESS_INFO* stream)
{
    for (int i = 0; i < 2; i++) {
        stream->Channels[i].wCode = 0;
        stream->Channels[i].wCodeBuf = 0;
        stream->Channels[i].wIndex = 0;
        stream->Channels[i].wStep = wCODECStepTab[0];
        stream->Channels[i].dwPredicted = 0;
        stream->Channels[i].dwSampleIndex = 0;
    }
}

/* Number of possible wIndex.  Comes from the fact that:
 *
 *   next_index = clamp(next_index, 0, 88);
 *
 * which means 0 <= index <= 88, hence 89 indexes.
 */
#define NUM_INDEXES 89

/* Number of possible nybbles.  Comes from the fact that:
 *
 *   next_nybble = wCodeBuf & 0xF
 *
 * which means 0 <= next_nybble <= 15, hence 16 possibilites.
 */
#define NUM_NYBBLES 16

/* Define a dynamic programming table mapping all possible indexes and nybbles
 * into their next value.  Pack things together into a struct so a cache miss
 * will retrieve both next index and diff value.
 *
 * This table should consume ~12kb, which is quite small.
 *
 */
static struct
{
    int diff;
    short index;
} SosDecompTable[NUM_INDEXES][NUM_NYBBLES];

/* Flag if above table was initialized.  */
static bool SosDecompTableGenerated = false;

/* Generate decompression table for samples.  Precompute every possible value
 * of dwDifference and Channels[0].wIndex based on every possible  combination
 * of index and nybble values.  */
void sosCODECGenerateDecompressTable(void)
{
    short index, nybble;
    int diff;

    for (index = 0; index < NUM_INDEXES; index++) {
        short step = wCODECStepTab[index];
        for (nybble = 0; nybble < NUM_NYBBLES; nybble++) {
            diff = step >> 3;

            if ((nybble & 4) != 0) {
                diff += step;
            }

            if ((nybble & 2) != 0) {
                diff += step >> 1;
            }

            if ((nybble & 1) != 0) {
                diff += step >> 2;
            }

            if ((nybble & 8) != 0) {
                diff = -diff;
            }

            short next_index = index + wCODECIndexTab[nybble & 0x7];
            next_index = clamp(next_index, 0, 88);

            SosDecompTable[index][nybble].diff = diff;
            SosDecompTable[index][nybble].index = next_index;
        }
    }
}

/* Template version of sosCODECDecompressData which generates a single version
   for 8-bits and 16-bits.  This instructs the compiler to avoid generating a
   branch in the deepest loop.  */
template <bool BITS_8>
static unsigned sosCODECDecompressDataTemplate(_SOS_COMPRESS_INFO* stream, unsigned bytes)
{
    const unsigned full_length = bytes;
    const int num_channels = stream->wChannels;

    if (num_channels <= 0)
    {
        return 0;
    }

    unsigned compressed_bytes = BITS_8 ? (bytes / 2) : (bytes / 4);
    unsigned iterations_per_channel = compressed_bytes / num_channels;

    if (iterations_per_channel == 0)
    {
        return full_length;
    }

    uint8_t* src = reinterpret_cast<uint8_t*>(stream->lpSource);
    int16_t* dst = reinterpret_cast<int16_t*>(stream->lpDest);

    for (int channel = 0; channel < num_channels; ++channel)
    {
        int16_t index = stream->Channels[channel].wIndex;
        int sample = stream->Channels[channel].dwPredicted;

        for (unsigned j = 0; j < iterations_per_channel; ++j)
        {
            uint8_t codebuf = *src;
            src += num_channels;

            uint8_t current_nybble = codebuf & 0xF;
            sample += SosDecompTable[index][current_nybble].diff;
            sample = clamp(sample, -32768, 32767);

            if (BITS_8)
            {
                uint8_t* dst8 = reinterpret_cast<uint8_t*>(dst);
                *dst8 = static_cast<uint8_t>(((sample & 0xFF00) >> 8) ^ 0x80);
                dst = reinterpret_cast<int16_t*>(dst8 + num_channels);
            }
            else
            {
                *dst = static_cast<int16_t>(sample);
                dst += num_channels;
            }
            index = SosDecompTable[index][current_nybble].index;

            current_nybble = codebuf >> 4;
            sample += SosDecompTable[index][current_nybble].diff;
            sample = clamp(sample, -32768, 32767);

            if (BITS_8)
            {
                uint8_t* dst8 = reinterpret_cast<uint8_t*>(dst);
                *dst8 = static_cast<uint8_t>(((sample & 0xFF00) >> 8) ^ 0x80);
                dst = reinterpret_cast<int16_t*>(dst8 + num_channels);
            }
            else
            {
                *dst = static_cast<int16_t>(sample);
                dst += num_channels;
            }
            index = SosDecompTable[index][current_nybble].index;
        }

        stream->Channels[channel].dwPredicted = sample;
        stream->Channels[channel].wIndex = index;

        src = reinterpret_cast<uint8_t*>(stream->lpSource) + 1;
        if (BITS_8)
        {
            dst = reinterpret_cast<int16_t*>(reinterpret_cast<uint8_t*>(stream->lpDest) + 1);
        }
        else
        {
            dst = reinterpret_cast<int16_t*>(stream->lpDest) + 1;
        }
    }

    return full_length;
}

//
// decompress data from a 4:1 ADPCM compressed file.  the number of
// bytes decompressed is returned.
//
//
unsigned sosCODECDecompressData(_SOS_COMPRESS_INFO* stream, unsigned bytes)
{
    if (SosDecompTableGenerated == false) {
        sosCODECGenerateDecompressTable();
        SosDecompTableGenerated = true;
    }

    if (stream->wBitSize == 16) {
        return sosCODECDecompressDataTemplate<false>(stream, bytes);
    }
#if 0 // No video or audio sample with this option?
    else {
        return sosCODECDecompressDataTemplate<true>(stream, bytes);
    }
#endif
    assert(0 && "Unreachable");
    return 0;
}

//
// Compresses a data stream into 4:1 ADPCM.  16 bit data is compressed 4:1
// 8 bit data is compressed 2:1.
//
unsigned int sosCODECCompressData(_SOS_COMPRESS_INFO* stream, unsigned int bytes)
{
    int delta;
    int tmp_step;
    short code;
    unsigned tmp;
    unsigned step;
    short current_samp;

    int samples = stream->wBitSize == 16 ? bytes >> 1 : bytes;
    stream->Channels[0].dwSampleIndex = 0;
    stream->Channels[1].dwSampleIndex = 0;
    short* src = (short*)(stream->lpSource);
    char* dst = stream->lpDest;

    if (stream->wChannels == 2) {
        // Compress a stereo data stream.
        for (int i = samples; i > 0; i -= 2) {
            if (stream->wBitSize == 16) {
                current_samp = *src;
                src += 2;
            } else {
                current_samp = *src;
                ++src;
                current_samp = (current_samp & 0xFF00) ^ 0x8000;
            }

            delta = current_samp - (stream->Channels[0].dwPredicted);
            code = 0;

            if (delta < 0) {
                delta = -delta;
                code = 8;
            }

            stream->Channels[0].wCode = code;
            tmp_step = stream->Channels[0].wStep;
            tmp = 4;

            for (int i = 3; i > 0; --i) {
                if (delta >= tmp_step) {
                    stream->Channels[0].wCode |= tmp;
                    delta -= tmp_step;
                }

                tmp_step = tmp_step >> 1;
                tmp >>= 1;
            };

            stream->Channels[0].dwDifference = delta;

            if (stream->Channels[0].dwSampleIndex & 1) {
                *dst = stream->Channels[0].wCodeBuf | (stream->Channels[0].wCode << 4);
                dst += 2;
            } else {
                stream->Channels[0].wCodeBuf = stream->Channels[0].wCode & 0xF;
            }

            step = stream->Channels[0].wStep;
            code = stream->Channels[0].wCode;
            stream->Channels[0].dwDifference = step >> 3;

            if (code & 4) {
                stream->Channels[0].dwDifference += step;
            }

            if (code & 2) {
                stream->Channels[0].dwDifference += step >> 1;
            }

            if (code & 1) {
                stream->Channels[0].dwDifference += step >> 2;
            }

            if (code & 8) {
                stream->Channels[0].dwDifference = -stream->Channels[0].dwDifference;
            }

            stream->Channels[0].dwPredicted =
                clamp(stream->Channels[0].dwDifference + stream->Channels[0].dwPredicted, -32768, 32767);
            stream->Channels[0].wIndex += wCODECIndexTab[stream->Channels[0].wCode];
            stream->Channels[0].wIndex = clamp(stream->Channels[0].wIndex, 0, 88);
            ++stream->Channels[0].dwSampleIndex;
            stream->Channels[0].wStep = wCODECStepTab[stream->Channels[0].wIndex];
        }

        src = (short*)(stream->lpSource + 1);
        dst = stream->lpDest + 1;

        if (stream->wBitSize == 16) {
            src = (short*)(stream->lpSource) + 1;
        }

        for (int i = samples; i > 0; i -= 2) {
            if (stream->wBitSize == 16) {
                current_samp = *src;
                src += 2;
            } else {
                current_samp = *src;
                ++src;
                current_samp = (current_samp & 0xFF00) ^ 0x8000;
            }

            delta = current_samp - (stream->Channels[1].dwPredicted);
            code = 0;

            if (delta < 0) {
                delta = -delta;
                code = 8;
            }

            stream->Channels[1].wCode = code;
            tmp_step = stream->Channels[1].wStep;
            tmp = 4;

            for (int i = 3; i > 0; --i) {
                if (delta >= tmp_step) {
                    stream->Channels[1].wCode |= tmp;
                    delta -= tmp_step;
                }

                tmp_step >>= 1;
                tmp >>= 1;
            };

            stream->Channels[1].dwDifference = delta;

            if (stream->Channels[1].dwSampleIndex & 1) {
                *dst = stream->Channels[1].wCodeBuf | (stream->Channels[1].wCode << 4);
                dst += 2;
            } else {
                stream->Channels[1].wCodeBuf = stream->Channels[1].wCode & 0xF;
            }

            step = stream->Channels[1].wStep;
            code = stream->Channels[1].wCode;
            stream->Channels[1].dwDifference = step >> 3;

            if (code & 4) {
                stream->Channels[1].dwDifference += step;
            }

            if (code & 2) {
                stream->Channels[1].dwDifference += step >> 1;
            }

            if (code & 1) {
                stream->Channels[1].dwDifference += step >> 2;
            }

            if (code & 8) {
                stream->Channels[1].dwDifference = -stream->Channels[1].dwDifference;
            }

            stream->Channels[1].dwPredicted =
                clamp(stream->Channels[1].dwDifference + stream->Channels[1].dwPredicted, -32768, 32767);
            stream->Channels[1].wIndex += wCODECIndexTab[stream->Channels[1].wCode];
            stream->Channels[1].wIndex = clamp(stream->Channels[1].wIndex, 0, 88);
            ++stream->Channels[1].dwSampleIndex;
            stream->Channels[1].wStep = wCODECStepTab[stream->Channels[1].wIndex];
        }
    } else {
        // Compress a mono data stream.
        for (int i = samples; i > 0; --i) {
            if (stream->wBitSize == 16) {
                current_samp = *src;
                ++src;
            } else {
                current_samp = *src;
                src = (short*)((char*)(src) + 1);
                current_samp = (current_samp & 0xFF00) ^ 0x8000;
            }

            delta = current_samp - (stream->Channels[0].dwPredicted);
            code = 0;

            if (delta < 0) {
                delta = -delta;
                code = 8;
            }

            stream->Channels[0].wCode = code;
            tmp_step = stream->Channels[0].wStep;
            tmp = 4;

            for (int i = 3; i > 0; --i) {
                if (delta >= tmp_step) {
                    stream->Channels[0].wCode |= tmp;
                    delta -= tmp_step;
                }

                tmp_step >>= 1;
                tmp >>= 1;
            }

            stream->Channels[0].dwDifference = delta;

            if (stream->Channels[0].dwSampleIndex & 1) {
                *dst++ = stream->Channels[0].wCodeBuf | (stream->Channels[0].wCode << 4);
            } else {
                stream->Channels[0].wCodeBuf = stream->Channels[0].wCode & 0xF;
            }

            step = stream->Channels[0].wStep;
            code = stream->Channels[0].wCode;
            stream->Channels[0].dwDifference = step >> 3;

            if (code & 4) {
                stream->Channels[0].dwDifference += step;
            }

            if (code & 2) {
                stream->Channels[0].dwDifference += step >> 1;
            }

            if (code & 1) {
                stream->Channels[0].dwDifference += step >> 2;
            }

            if (code & 8) {
                stream->Channels[0].dwDifference = -stream->Channels[0].dwDifference;
            }

            stream->Channels[0].dwPredicted =
                clamp(stream->Channels[0].dwDifference + stream->Channels[0].dwPredicted, -32768, 32767);
            stream->Channels[0].wIndex += wCODECIndexTab[stream->Channels[0].wCode];
            stream->Channels[0].wIndex = clamp(stream->Channels[0].wIndex, 0, 88);
            ++stream->Channels[0].dwSampleIndex;
            stream->Channels[0].wStep = wCODECStepTab[stream->Channels[0].wIndex];
        }
    }

    return stream->wBitSize == 16 ? bytes >> 2 : bytes >> 1;
}
