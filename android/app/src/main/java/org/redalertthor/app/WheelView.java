package org.redalertthor.app;

import android.graphics.*;
import android.view.View;

/** Generals-style wheels: left stick chooses, A confirms, shoulder release closes. */
final class WheelView extends View {
    private final ThorActivity owner;
    private final Paint p = new Paint(3);
    private boolean visible, groups;
    private int chosen = -1, page;
    private final String[] commands = {"Guard", "Stop", "Scatter", "Deploy / unload", "Repair", "Sell", "Select view", "Deselect"};
    WheelView(ThorActivity activity) { super(activity); owner = activity; setFocusable(false); }
    boolean open() { return visible; }
    boolean groups() { return groups; }
    int choice() { return visible && chosen>=0 ? page*8+chosen : -1; }
    void show(boolean groupWheel) { groups = groupWheel; visible = true; chosen = -1; page=0; owner.stopAxes(); invalidate(); }
    void cancel() { visible = false; chosen = -1; invalidate(); }
    void navigate(int dx) { if(groups && dx!=0) { page=dx>0?1:0; invalidate(); } }
    void choose(float x, float y) {
        chosen = Math.hypot(x, y) < .3 ? -1 : ((int)Math.floor((Math.atan2(x, -y) + Math.PI * 2 + Math.PI / 8) / (Math.PI / 4))) % 8;
        invalidate();
    }
    void groupAction(int action) {
        int index=choice();
        if(groups && index>=0 && index<10) ThorActivity.command(12,index,action,0,0);
    }
    void confirm() {
        if (!visible) return;
        if (groups) { groupAction(0); return; }
        int index = chosen; visible = false; invalidate();
        if (index < 0) return;
        if (!enabled(index)) return;
        switch (index) {
        case 0: owner.key(10); break;
        case 1: owner.key(22); break;
        case 2: owner.key(27); break;
        case 3: owner.action(4); break;
        case 4: owner.action(2); break;
        case 5: owner.action(3); break;
        case 6: owner.action(5); break;
        case 7: owner.action(0); break;
        }
    }
    private boolean enabled(int i) {
        if (groups) return page*8+i<10;
        switch (i) {
        case 0: return owner.latest.optBoolean("canMove") && owner.latest.optBoolean("canFire");
        case 1: return owner.latest.optBoolean("canMove") || owner.latest.optBoolean("canFire");
        case 2: return owner.latest.optBoolean("canMove");
        case 3: return owner.latest.optBoolean("deploy");
        case 4: case 5: return owner.latest.optInt("buildings")>0;
        case 7: return owner.latest.optInt("selected")>0;
        default: return true;
        }
    }
    @Override protected void onDraw(Canvas c) {
        if (!visible) return;
        c.drawColor(0x9904080a);
        float cx = getWidth()/2f, cy = getHeight()/2f, radius = Math.min(getWidth(), getHeight()) * .39f;
        for (int i = 0; i < 8; ++i) {
            double angle = i * Math.PI/4;
            float x = cx + (float)Math.sin(angle) * radius, y = cy - (float)Math.cos(angle) * radius;
            float w = radius * .63f, h = radius * .25f;
            RectF box = new RectF(x - w/2, y - h/2, x+w/2, y+h/2);
            p.setColor(chosen == i ? 0xff7f2725 : 0xff15282d); p.setStyle(Paint.Style.FILL); c.drawRoundRect(box, 18, 18, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(3); p.setColor(chosen == i ? 0xffffd38d : 0xff45646b); c.drawRoundRect(box, 18, 18, p); p.setStyle(Paint.Style.FILL);
            p.setColor(enabled(i)?Color.WHITE:0xff71878d); p.setTextAlign(Paint.Align.CENTER); p.setTextSize(radius * .069f);
            String label=commands[i];
            if (groups) {
                org.json.JSONArray counts=owner.latest.optJSONArray("groups");
                int index=page*8+i;
                label=index<10?"Group "+(index+1)+" · "+(counts==null?0:counts.optInt(index)):"—";
            }
            c.drawText(label, x, y + p.getTextSize()*.33f, p);
        }
        p.setTextAlign(Paint.Align.CENTER); p.setColor(Color.WHITE); p.setTypeface(Typeface.DEFAULT_BOLD); p.setTextSize(radius*.09f);
        c.drawText(groups ? "GROUPS" : "COMMANDS", cx, cy-12, p);
        p.setTypeface(Typeface.DEFAULT); p.setTextSize(radius*.062f); p.setColor(0xffc2d0d1);
        c.drawText("Left stick · A to confirm · B to cancel", cx, cy+26, p);
        c.drawText(groups ? "X assign · LT+X add · Y center" : "Release RT to close", cx, cy+58, p);
        if(groups) c.drawText("D-pad left/right · groups "+(page==0?"1–8":"9–10"),cx,cy+90,p);
    }
}
