package org.redalertthor.app;
import android.content.*;
import java.io.*;

/** Debug builds only. Production APKs have no exported input or telemetry receiver. */
public final class QaReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (ThorActivity.current == null) { setResultData("game activity is not running"); return; }
        try {
            if (intent.hasExtra("kind")) ThorActivity.command(intent.getIntExtra("kind",0),intent.getIntExtra("a",0),intent.getIntExtra("b",0),intent.getFloatExtra("x",0),intent.getFloatExtra("y",0));
            if (intent.hasExtra("key")) ThorActivity.current.key(intent.getIntExtra("key",41));
            File file = new File(context.getExternalFilesDir(null),"qa-state.json");
            try (FileWriter out = new FileWriter(file)) { out.write(ThorActivity.current.diagnosticState()); }
            setResultData("ok");
        } catch (Exception error) { setResultData(error.toString()); }
    }
}
