package org.redalertthor.app;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.app.Presentation;
import android.hardware.display.DisplayManager;
import android.view.*;
import android.widget.FrameLayout;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONObject;
import org.libsdl.app.SDLActivity;

public final class ThorActivity extends SDLActivity {
    static ThorActivity current;
    public static native void configure(String root);
    public static native void command(int kind, int a, int b, float x, float y);
    public static native String state();
    public static native int[] radar();
    public static native int[] icon(int type, int id);
    private final Handler handler = new Handler(Looper.getMainLooper());
    JSONObject latest = new JSONObject();
    private Presentation bottom;
    private DisplayManager displayManager;
    private DisplayManager.DisplayListener displayListener;
    private CommandDeck deck;
    private WheelView wheel;
    private volatile boolean ready;
    private boolean lt, rt, lb, r3, selecting, resumed, controllerActive;
    private boolean ltDigital, rtDigital, ltAnalog, rtAnalog, deckPress;
    private int hatX, hatY;
    private long lastNavigation;
    private long lastStateRead;
    private float lx, ly, rx, ry;
    private boolean twoTouch;
    private float touchX, touchY, pinch;
    private long touchStarted;
    private float touchTravel;
    private int ignoredARepeats;
    private static final int EXPORT_SAVES = 701;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (ready && resumed) {
                try {
                    long now = android.os.SystemClock.uptimeMillis();
                    if (now - lastStateRead >= 100) {
                        lastStateRead = now; latest = new JSONObject(state());
                        if (deck != null) deck.update(latest, radar());
                    }
                    sendAxes();
                } catch (org.json.JSONException error) { android.util.Log.e("RedAlertThor", "Invalid engine snapshot", error); }
            }
            handler.postDelayed(this, 16);
        }
    };
    @Override protected String[] getLibraries() { return new String[]{"SDL2", "openal", "vanillara"}; }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        current = this;
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        wheel = new WheelView(this);
        addContentView(wheel, new android.view.ViewGroup.LayoutParams(-1, -1));
        displayManager = (DisplayManager)getSystemService(DISPLAY_SERVICE);
        displayListener = new DisplayManager.DisplayListener() {
            @Override public void onDisplayAdded(int id) { showBottom(); }
            @Override public void onDisplayRemoved(int id) { if (bottom != null && bottom.getDisplay().getDisplayId() == id) { bottom.dismiss(); bottom = null; } }
            @Override public void onDisplayChanged(int id) { }
        };
        displayManager.registerDisplayListener(displayListener, handler);
        showBottom(); handler.post(tick);
    }
    @Override protected String[] getArguments() {
        File root = getExternalFilesDir(null);
        configure(root.getAbsolutePath());
        ready = true;
        return new String[]{"-CD" + new File(root,"game").getAbsolutePath()};
    }
    private void showBottom() {
        if (bottom != null) { bottom.show(); return; }
        DisplayManager manager = (DisplayManager)getSystemService(DISPLAY_SERVICE);
        for (Display display : manager.getDisplays()) {
            if (display.getDisplayId() == Display.DEFAULT_DISPLAY) continue;
            bottom = new Presentation(this, display);
            deck = new CommandDeck(this, bottom.getContext());
            bottom.setContentView(deck);
            if (bottom.getWindow() != null) bottom.getWindow().setFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE);
            bottom.show(); bottom.getWindow().getDecorView().setSystemUiVisibility(5894);
            break;
        }
    }
    @Override protected void onResume() { super.onResume(); resumed = true; showBottom(); }
    @Override protected void onPause() { release(); resumed = false; if (bottom != null) bottom.hide(); super.onPause(); }
    @Override protected void onDestroy() {
        current = null;
        if (displayManager != null && displayListener != null) displayManager.unregisterDisplayListener(displayListener);
        handler.removeCallbacksAndMessages(null);
        if (bottom != null) bottom.dismiss();
        super.onDestroy();
    }
    private void release() {
        if (ready) command(8, 0, 0, 0, 0);
        lt = rt = lb = r3 = selecting = controllerActive = false; lx = ly = rx = ry = 0;
        ltDigital = rtDigital = ltAnalog = rtAnalog = deckPress = false; hatX = hatY = 0;
        if (wheel != null) wheel.cancel();
    }
    void key(int scancode) {
        if (!ready) return;
        command(2, scancode, 0, 0, 0);
        handler.postDelayed(() -> command(2, scancode, 1, 0, 0), 45);
    }
    void action(int id) { if (ready) command(5, id, 0, 0, 0); }
    void exportSaves() {
        release();
        android.content.Intent intent = new android.content.Intent(android.content.Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(android.content.Intent.CATEGORY_OPENABLE);
        intent.setType("application/zip");
        intent.putExtra(android.content.Intent.EXTRA_TITLE, "RedAlert-Thor-saves-" + System.currentTimeMillis() + ".zip");
        startActivityForResult(intent, EXPORT_SAVES);
    }
    @Override protected void onActivityResult(int request, int result, android.content.Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT_SAVES || result != RESULT_OK || data == null || data.getData() == null) return;
        android.net.Uri destination = data.getData();
        File folder = new File(getExternalFilesDir(null), "user/vanillara");
        new Thread(() -> {
            String message;
            try (OutputStream output = getContentResolver().openOutputStream(destination);
                 ZipOutputStream zip = new ZipOutputStream(output)) {
                File[] files = folder.listFiles();
                if (files == null) throw new java.io.IOException("Save folder is unavailable");
                byte[] buffer = new byte[65536];
                for (File file : files) if (file.isFile()) {
                    zip.putNextEntry(new ZipEntry("vanillara/" + file.getName()));
                    try (FileInputStream input = new FileInputStream(file)) {
                        int count; while ((count = input.read(buffer)) != -1) zip.write(buffer, 0, count);
                    }
                    zip.closeEntry();
                }
                message = "Saves exported";
            } catch (Exception error) {
                android.util.Log.e("RedAlertThor", "Save export failed", error);
                message = "Could not export saves. Choose another location and try again.";
            }
            final String notice = message;
            handler.post(() -> android.widget.Toast.makeText(this, notice, android.widget.Toast.LENGTH_LONG).show());
        }, "save-export").start();
    }
    void touch() { controllerActive=false; stopAxes(); }
    void stopAxes() { command(3,0,0,0,0); command(16,0,0,0,0); }
    private void sendAxes() {
        if (!controllerActive || wheel.open()) stopAxes();
        else if (deck!=null && deck.radarMode()) { stopAxes(); deck.moveRadar(lx,ly); }
        else {
            command(3,0,0,lx,ly);
            // Keep a selection box anchored while A is held.
            boolean camera = !selecting && latest.optBoolean("active") && !latest.optBoolean("modal");
            command(16,0,0,camera && !r3?rx:0,camera && !r3?ry:0);
            if (camera && r3 && ry!=0) command(7,0,0,-ry*.025f,0);
        }
    }
    String diagnosticState() throws org.json.JSONException {
        JSONObject result = new JSONObject(state());
        result.put("leftX",lx); result.put("leftY",ly); result.put("rightX",rx); result.put("rightY",ry);
        result.put("leftTrigger",lt); result.put("rightTrigger",rt);
        result.put("zoomModifier",r3);
        result.put("selecting",selecting);
        result.put("ignoredARepeats",ignoredARepeats);
        result.put("wheelGroups",wheel.open() && wheel.groups());
        result.put("wheelChoice",wheel.choice());
        result.put("wheel",wheel.open()?"open":"closed");
        return result.toString();
    }
    private void click(boolean down, int button) { if (ready) command(1, button, down ? 0 : 1, -1, -1); }
    private void trigger(boolean left, boolean held) {
        if (left) {
            if (lt == held) return; lt = held;
            command(2, 225, held ? 0 : 1, 0, 0); // SDL left Shift: native additive selection.
        } else {
            if (rt == held) return; rt = held;
            if (held && latest.optBoolean("active") && !latest.optBoolean("modal")) wheel.show(false);
            else if (!held && !wheel.groups()) wheel.cancel();
        }
    }
    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        int code = e.getKeyCode();
        boolean down = e.getAction() == KeyEvent.ACTION_DOWN;
        if (!ready) return super.dispatchKeyEvent(e);
        if(KeyEvent.isGamepadButton(code) || code>=KeyEvent.KEYCODE_DPAD_UP && code<=KeyEvent.KEYCODE_DPAD_RIGHT) controllerActive=true;
        switch (code) {
        case KeyEvent.KEYCODE_BUTTON_A:
            // A physical hold repeats on Android. Only its first DOWN starts a
            // native mouse press; another press would restart the selection box.
            if (down && e.getRepeatCount()!=0) { ++ignoredARepeats; return true; }
            if (!down && deckPress) { deckPress = false; return true; }
            if (wheel.open()) { if (down && e.getRepeatCount() == 0) { deckPress=true; wheel.confirm(); } return true; }
            if (deck != null && deck.radarMode()) { if (down && e.getRepeatCount()==0) { deckPress=true; deck.useRadar(); } return true; }
            if (down && deck != null && deck.activateFocus()) { deckPress = true; return true; }
            selecting = down; sendAxes(); click(down, 1); return true;
        case KeyEvent.KEYCODE_BUTTON_B:
            if (down && e.getRepeatCount() == 0) {
                if (wheel.open()) wheel.cancel();
                else if (deck != null && deck.radarMode()) deck.toggleRadar();
                else if (latest.optBoolean("modal")) key(41);
                else if (latest.optBoolean("active")) command(14,0,0,0,0);
                else key(41);
                if (deck != null) deck.clearDeckFocus();
            } return true;
        case KeyEvent.KEYCODE_BUTTON_X:
            if (down && e.getRepeatCount() == 0) { if (wheel.open()) wheel.groupAction(lt ? 2 : 1); else key(10); } return true; // G
        case KeyEvent.KEYCODE_BUTTON_Y:
            if (down && e.getRepeatCount() == 0) { if (wheel.open()) wheel.groupAction(3); else key(22); } return true; // S
        case KeyEvent.KEYCODE_BUTTON_L2: ltDigital = down; trigger(true, down || ltAnalog); return true;
        case KeyEvent.KEYCODE_BUTTON_R2: rtDigital = down; trigger(false, down || rtAnalog); return true;
        case KeyEvent.KEYCODE_BUTTON_L1:
            if (lb != down) { lb = down; if (down && latest.optBoolean("active") && !latest.optBoolean("modal")) wheel.show(true); else if (!down && wheel.groups()) wheel.cancel(); } return true;
        case KeyEvent.KEYCODE_BUTTON_R1: if (down && e.getRepeatCount() == 0 && deck != null) deck.toggleRadar(); return true;
        case KeyEvent.KEYCODE_BUTTON_THUMBL:
            if (down && e.getRepeatCount()==0) {
                if (!selecting) action(lt?6:1);
                if (deck!=null) deck.clearDeckFocus();
            }
            return true;
        case KeyEvent.KEYCODE_BUTTON_THUMBR: r3 = down; sendAxes(); return true;
        case KeyEvent.KEYCODE_BUTTON_START: if (down && e.getRepeatCount() == 0) key(41); return true;
        case KeyEvent.KEYCODE_BUTTON_SELECT: if (down && e.getRepeatCount() == 0 && deck != null) deck.nextTab(); return true;
        case KeyEvent.KEYCODE_DPAD_UP: case KeyEvent.KEYCODE_DPAD_DOWN: case KeyEvent.KEYCODE_DPAD_LEFT: case KeyEvent.KEYCODE_DPAD_RIGHT:
            if (down) {
                int dx = code == KeyEvent.KEYCODE_DPAD_LEFT ? -1 : code == KeyEvent.KEYCODE_DPAD_RIGHT ? 1 : 0;
                int dy = code == KeyEvent.KEYCODE_DPAD_UP ? -1 : code == KeyEvent.KEYCODE_DPAD_DOWN ? 1 : 0;
                navigate(dx,dy);
            } return true;
        default: return super.dispatchKeyEvent(e);
        }
    }
    private static float dead(float v) { return Math.abs(v) < .18f ? 0 : Math.signum(v) * (Math.abs(v) - .18f) / .82f; }
    private void navigate(int dx, int dy) {
        long now = android.os.SystemClock.uptimeMillis(); if (now-lastNavigation < 100) return;
        lastNavigation = now;
        if (wheel.open()) wheel.navigate(dx);
        else if (latest.optBoolean("active") && !latest.optBoolean("modal") && !lt && deck != null) deck.navigate(dx,dy);
        else command(11,dx,dy,0,0);
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent e) {
        if (ready && (e.isFromSource(InputDevice.SOURCE_JOYSTICK) || e.isFromSource(InputDevice.SOURCE_GAMEPAD))) {
            controllerActive=true;
            lx = dead(e.getAxisValue(MotionEvent.AXIS_X)); ly = dead(e.getAxisValue(MotionEvent.AXIS_Y));
            if ((lx != 0 || ly != 0) && deck != null) deck.clearDeckFocus();
            rx = dead(e.getAxisValue(MotionEvent.AXIS_Z)); ry = dead(e.getAxisValue(MotionEvent.AXIS_RZ));
            ltAnalog = Math.max(e.getAxisValue(MotionEvent.AXIS_LTRIGGER), e.getAxisValue(MotionEvent.AXIS_BRAKE)) > .55f;
            rtAnalog = Math.max(e.getAxisValue(MotionEvent.AXIS_RTRIGGER), e.getAxisValue(MotionEvent.AXIS_GAS)) > .55f;
            trigger(true, ltAnalog || ltDigital); trigger(false, rtAnalog || rtDigital);
            int hx = Math.round(e.getAxisValue(MotionEvent.AXIS_HAT_X)), hy = Math.round(e.getAxisValue(MotionEvent.AXIS_HAT_Y));
            if ((hx!=hatX || hy!=hatY) && (hx!=0 || hy!=0)) navigate(hx,hy);
            hatX=hx; hatY=hy;
            if (wheel.open()) wheel.choose(lx, ly);
            return true;
        }
        return super.dispatchGenericMotionEvent(e);
    }
    private float[] gamePoint(float x, float y) {
        View decor = getWindow().getDecorView();
        float gw = Math.max(1, latest.optInt("width", 640)), gh = Math.max(1, latest.optInt("height", 400));
        float scale = Math.min(decor.getWidth() / gw, decor.getHeight() / gh), zoom = (float)latest.optDouble("zoom", 1);
        float px = (x - (decor.getWidth() - gw * scale) / 2) / scale;
        float py = (y - (decor.getHeight() - gh * scale) / 2) / scale;
        return new float[]{Math.max(0, Math.min(gw - 1, gw / 2 + (px - gw / 2) / zoom)), Math.max(0, Math.min(gh - 1, gh / 2 + (py - gh / 2) / zoom))};
    }
    @Override public boolean dispatchTouchEvent(MotionEvent e) {
        if (!ready || !e.isFromSource(InputDevice.SOURCE_TOUCHSCREEN)) return super.dispatchTouchEvent(e);
        int event = e.getActionMasked();
        if (wheel.open()) return true;
        if (event == MotionEvent.ACTION_DOWN) {
            touch();
            twoTouch = false; touchTravel = 0; touchStarted = e.getEventTime();
            touchX = e.getX(); touchY = e.getY(); float[] p = gamePoint(touchX, touchY);
            command(1, 1, 0, p[0], p[1]); return true;
        }
        if (event == MotionEvent.ACTION_POINTER_DOWN && e.getPointerCount() == 2) {
            float[] p = gamePoint(touchX, touchY); command(1, 1, 1, p[0], p[1]);
            twoTouch = true; touchX = (e.getX(0) + e.getX(1)) / 2; touchY = (e.getY(0) + e.getY(1)) / 2;
            pinch = (float)Math.hypot(e.getX(0) - e.getX(1), e.getY(0) - e.getY(1)); return true;
        }
        if (event == MotionEvent.ACTION_MOVE) {
            if (twoTouch && e.getPointerCount() >= 2) {
                float x = (e.getX(0) + e.getX(1)) / 2, y = (e.getY(0) + e.getY(1)) / 2;
                float distance = (float)Math.hypot(e.getX(0) - e.getX(1), e.getY(0) - e.getY(1));
                touchTravel += Math.hypot(x - touchX, y - touchY);
                command(10, 0, 0, (touchX - x) * 4 / (float)latest.optDouble("zoom", 1), (touchY - y) * 4 / (float)latest.optDouble("zoom", 1));
                command(7, 0, 0, (distance - pinch) / 600, 0); pinch = distance; touchX = x; touchY = y;
            } else if (!twoTouch) { float[] p = gamePoint(e.getX(), e.getY()); command(9, 0, 0, p[0], p[1]); }
            return true;
        }
        if (event == MotionEvent.ACTION_UP || event == MotionEvent.ACTION_CANCEL) {
            if (!twoTouch) { float[] p = gamePoint(e.getX(), e.getY()); command(1, 1, 1, p[0], p[1]); }
            else if (event != MotionEvent.ACTION_CANCEL && e.getEventTime() - touchStarted < 350 && touchTravel < 25) action(0);
            return true;
        }
        return true;
    }
}
