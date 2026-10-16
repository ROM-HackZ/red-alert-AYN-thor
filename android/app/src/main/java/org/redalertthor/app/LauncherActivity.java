package org.redalertthor.app;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.graphics.Color;
import android.widget.*;
import java.io.File;

/** A missing or interrupted import must show setup, never crash inside the engine. */
public final class LauncherActivity extends Activity {
    private static final String[] REQUIRED = {"REDALERT.MIX", "EXPAND.MIX", "EXPAND2.MIX", "HIRES1.MIX", "LORES1.MIX",
            "allied/MAIN.MIX", "soviet/MAIN.MIX", "counterstrike/MAIN.MIX", "aftermath/MAIN.MIX"};
    @Override protected void onCreate(Bundle state) { super.onCreate(state); openOrExplain(); }
    private void openOrExplain() {
        File game = new File(getExternalFilesDir(null), "game");
        boolean ready = true;
        for (String name : REQUIRED) if (new File(game, name).length() < 1000) ready = false;
        if (ready) {
            startActivity(new Intent(this, ThorActivity.class)); finish(); return;
        }
        LinearLayout box = new LinearLayout(this); box.setOrientation(1); box.setPadding(48, 40, 48, 40);
        box.setBackgroundColor(Color.rgb(13, 23, 25));
        TextView heading = new TextView(this); heading.setText("RED ALERT / THOR"); heading.setTextSize(30); heading.setTextColor(Color.WHITE); box.addView(heading);
        TextView body = new TextView(this); body.setText("Bring your Red Alert installation\n\nRun the desktop setup tool, choose your Steam game folder and connect your Thor by USB.\n\nSetup includes the original campaigns, Counterstrike and Aftermath. Your game files stay separate from the app.");
        body.setTextColor(Color.rgb(195, 210, 210)); body.setTextSize(20); body.setPadding(0, 30, 0, 30); box.addView(body);
        Button retry = new Button(this); retry.setText("Check installation"); retry.setOnClickListener(v -> openOrExplain()); box.addView(retry);
        setContentView(box);
    }
}
