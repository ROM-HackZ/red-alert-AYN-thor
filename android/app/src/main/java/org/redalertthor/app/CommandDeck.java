package org.redalertthor.app;

import android.content.Context;
import android.graphics.*;
import android.os.Handler;
import android.view.*;
import org.json.*;
import java.util.ArrayList;
import java.util.HashMap;

/** A native-state command deck. No OCR, screen crops or injected coordinates. */
final class CommandDeck extends View {
    private final ThorActivity owner;
    private final Paint p = new Paint(3);
    private JSONObject data = new JSONObject();
    private final ArrayList<JSONObject> items = new ArrayList<>();
    private final ArrayList<RectF> hit = new ArrayList<>();
    private Bitmap radar;
    private final HashMap<Integer,Bitmap> icons = new HashMap<>();
    private String scenario = "";
    private int tab, page, focus = -1;
    private boolean radarMode, longPressed, radarDrag;
    private float radarX=.5f, radarY=.5f;
    private float sx, sy, startY;
    private int held = -1;
    private final Handler handler = new Handler();
    private final String[] tabs = {"COMMANDS", "BUILD & TRAIN", "POWERS"};
    private final String[] commands = {"Guard", "Stop", "Scatter", "Deploy / unload", "Repair", "Sell", "Select view", "Same type", "Center selection", "Base", "Deselect"};
    private final String[] descriptions = {"Defend this area", "Cancel current orders", "Spread units apart", "Use selected unit's ability", "Choose a damaged building", "Choose a building to sell", "Units on this screen", "Selected type on screen", "Find selected units", "Find your yard or MCV", "Clear current selection"};
    CommandDeck(ThorActivity activity, Context context) { super(context); owner = activity; setFocusable(false); }
    void update(JSONObject value, int[] pixels) {
        data = value; items.clear(); JSONArray source = data.optJSONArray("build");
        if (!data.optBoolean("active") || data.optBoolean("modal")) { focus=-1; radarMode=false; }
        if (!data.optBoolean("radar")) radarMode=false;
        if (!scenario.equals(data.optString("scenario"))) { scenario = data.optString("scenario"); icons.clear(); }
        if (source != null) for (int i=0; i<source.length(); ++i) {
            JSONObject item = source.optJSONObject(i);
            if (item != null && ((tab == 2) == item.optBoolean("special"))) {
                items.add(item); int key = item.optInt("type")*1000+item.optInt("id");
                if (!icons.containsKey(key)) {
                    int[] image = ThorActivity.icon(item.optInt("type"),item.optInt("id"));
                    if (image.length > 2 && image.length == image[0]*image[1]+2)
                        icons.put(key,Bitmap.createBitmap(image,2,image[0],image[0],image[1],Bitmap.Config.ARGB_8888));
                }
            }
        }
        int w = data.optInt("mapW"), h = data.optInt("mapH");
        if (w > 0 && h > 0 && pixels.length == w*h) {
            if (radar == null || radar.getWidth()!=w || radar.getHeight()!=h) radar = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
            radar.setPixels(pixels,0,w,0,0,w,h);
        } else radar = null;
        page = Math.min(page, Math.max(0, (count()-1)/12)); invalidate();
    }
    private int count() { return tab == 0 ? commands.length : items.size(); }
    void nextTab() { tab = (tab+1)%3; page=0; focus=-1; update(data, new int[0]); }
    void toggleRadar() { radarMode = data.optBoolean("radar") && !data.optBoolean("modal") && !radarMode; invalidate(); }
    boolean radarMode() { return radarMode; }
    void moveRadar(float x,float y) { if (x==0 && y==0) return; radarX=Math.max(0,Math.min(1,radarX+x*.009f)); radarY=Math.max(0,Math.min(1,radarY+y*.009f)); invalidate(); }
    void useRadar() { ThorActivity.command(6,0,0,radarX,radarY); }
    void navigate(int dx, int dy) {
        if (count()==0) { focus=-1; return; }
        if (dx != 0) { page = Math.max(0, Math.min(Math.max(0,(count()-1)/12), page+dx)); focus=-1; }
        else focus = Math.max(0, Math.min(Math.min(12,count()-page*12)-1, focus + (dy > 0 ? 1 : -1)));
        invalidate();
    }
    boolean activateFocus() { if (focus < 0 || !data.optBoolean("active") || data.optBoolean("modal")) return false; activate(page*12+focus, false); return true; }
    void clearDeckFocus() { focus = -1; }
    private boolean enabled(int index) {
        if (!data.optBoolean("active") || data.optBoolean("modal")) return false;
        if (tab != 0) return index < items.size() && !items.get(index).optBoolean("busy");
        if (index == 3) return data.optBoolean("deploy");
        if (index == 0) return data.optBoolean("canMove") && data.optBoolean("canFire");
        if (index == 1) return data.optBoolean("canMove") || data.optBoolean("canFire");
        if (index == 2) return data.optBoolean("canMove");
        if (index == 4 || index == 5) return data.optInt("buildings")>0;
        return index == 4 || index == 5 || index == 6 || index == 9 || data.optInt("selected") > 0;
    }
    private void activate(int index, boolean cancel) {
        if (index < 0 || index >= count() || !enabled(index)) return;
        if (tab != 0) {
            JSONObject item = items.get(index);
            ThorActivity.command(4,item.optInt("type"),item.optInt("id"),cancel?1:0,0); return;
        }
        switch (index) {
        case 0: owner.key(10); break; case 1: owner.key(22); break; case 2: owner.key(27); break;
        case 3: owner.action(4); break; case 4: owner.action(2); break; case 5: owner.action(3); break;
        case 6: owner.action(5); break; case 7: owner.action(6); break; case 8: owner.action(1); break;
        case 9: owner.key(11); break; case 10: owner.action(0); break;
        }
    }
    private void text(Canvas c, String text, float x, float y, float size, int color, boolean bold) {
        p.setColor(color); p.setTextSize(size); p.setTypeface(bold?Typeface.DEFAULT_BOLD:Typeface.DEFAULT); p.setTextAlign(Paint.Align.LEFT);
        c.drawText(text,x,y,p);
    }
    private void box(Canvas c, RectF r, int color) { p.setColor(color); p.setStyle(Paint.Style.FILL); c.drawRoundRect(r,14,14,p); }
    private RectF radarBounds() {
        float w=data.optInt("mapW"), h=data.optInt("mapH");
        if (w<=0 || h<=0) return new RectF(24,214,374,564);
        float scale=350/Math.max(w,h), rw=w*scale, rh=h*scale;
        return new RectF(199-rw/2,389-rh/2,199+rw/2,389+rh/2);
    }
    private String fit(String s, float width, float size) {
        p.setTextSize(size); if (p.measureText(s)<=width) return s;
        while (s.length()>1 && p.measureText(s+"…")>width) s=s.substring(0,s.length()-1);
        return s+"…";
    }
    @Override protected void onDraw(Canvas canvas) {
        sx=getWidth()/1240f; sy=getHeight()/1080f;
        canvas.save(); canvas.scale(sx,sy); canvas.drawColor(0xff0c171c);
        text(canvas,"RED ALERT",32,54,31,0xfff4eee5,true);
        text(canvas,"THOR COMMAND DECK",32,87,17,0xff87a4ad,false);
        text(canvas,"$ "+data.optInt("money"),690,50,30,0xffe8d08b,true);
        text(canvas,"POWER  "+data.optInt("power")+" / "+data.optInt("drain"),900,50,21,data.optInt("power")<data.optInt("drain")?0xffff8b79:0xff9fcdc1,true);
        for (int i=0;i<3;++i) {
            RectF r=new RectF(24+i*405,112,405+i*405,180); box(canvas,r,tab==i?0xff782c2a:0xff1b3038);
            text(canvas,tabs[i],r.left+25,155,25,0xfff3f1ea,true);
        }
        RectF map=new RectF(24,214,374,564); box(canvas,map,0xff14252c);
        if (radar!=null) {
            map=radarBounds();
            p.setFilterBitmap(false); canvas.drawBitmap(radar,null,map,p);
            float mw=data.optInt("mapW")*256f,mh=data.optInt("mapH")*256f;
            float zoom=(float)Math.max(1,data.optDouble("zoom",1));
            float cw=data.optInt("cameraW",2800)/zoom, ch=data.optInt("cameraH",1800)/zoom;
            float x=(data.optInt("cameraX")+(data.optInt("cameraW",2800)-cw)/2-data.optInt("mapX")*256f)/mw;
            float y=(data.optInt("cameraY")+(data.optInt("cameraH",1800)-ch)/2-data.optInt("mapY")*256f)/mh;
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(3); p.setColor(0xfff4e7b7);
            canvas.save(); canvas.clipRect(map);
            canvas.drawRect(map.left+x*map.width(),map.top+y*map.height(),map.left+(x+cw/mw)*map.width(),map.top+(y+ch/mh)*map.height(),p); p.setStyle(Paint.Style.FILL);
            canvas.restore();
            if (radarMode) {
                p.setColor(0xffffce76); p.setStrokeWidth(3);
                float tx=map.left+radarX*map.width(),ty=map.top+radarY*map.height();
                canvas.drawLine(tx-15,ty,tx+15,ty,p); canvas.drawLine(tx,ty-15,tx,ty+15,p);
            }
        } else {
            text(canvas,"RADAR OFFLINE",64,378,24,0xff72909a,true);
            text(canvas,"Requires an active radar",47,414,19,0xff72909a,false);
        }
        text(canvas,"SELECTION",28,618,18,0xff91aeb6,true);
        text(canvas,fit(data.optString("selection","No selection"),340,27),28,660,27,Color.WHITE,true);
        text(canvas,data.optInt("selected")+" selected",28,697,22,0xffa9c2c7,false);
        text(canvas,data.optBoolean("targeting")?"CHOOSE A TARGET":"BATTLEFIELD READY",28,763,18,0xffe0bd82,true);
        text(canvas,"A  Select / order / drag",28,824,20,0xffa9c2c7,false);
        text(canvas,"B  Cancel / deselect",28,861,20,0xffa9c2c7,false);
        text(canvas,"RT  Commands   LB  Groups",28,898,20,0xffa9c2c7,false);
        text(canvas,"LT  Add to selection",28,935,20,0xffa9c2c7,false);
        text(canvas,"Hold L3 + left stick: cursor",28,972,20,0xffa9c2c7,false);
        hit.clear();
        int start=page*12, total=count();
        for (int slot=0;slot<12 && start+slot<total;++slot) {
            int index=start+slot, col=slot%3,row=slot/3;
            RectF r=new RectF(402+col*270,214+row*176,652+col*270,374+row*176); hit.add(r);
            boolean allowed=enabled(index); JSONObject item=tab==0?null:items.get(index);
            box(canvas,r,focus==slot?0xff6a3830:allowed?0xff20363f:0xff17272d);
            p.setColor(focus==slot?0xffffd398:0xff3c5660); p.setStrokeWidth(focus==slot?3:1); p.setStyle(Paint.Style.STROKE); canvas.drawRoundRect(r,14,14,p); p.setStyle(Paint.Style.FILL);
            String name=tab==0?commands[index]:item.optString("name");
            Bitmap icon=item==null?null:icons.get(item.optInt("type")*1000+item.optInt("id"));
            if (icon!=null) { p.setFilterBitmap(false); canvas.drawBitmap(icon,null,new RectF(r.left+12,r.top+10,r.left+112,r.top+85),p); }
            text(canvas,fit(name,r.width()-24,item==null?24:21),r.left+12,r.top+(item==null?43:113),item==null?24:21,allowed?Color.WHITE:0xff819399,true);
            String sub=tab==0?descriptions[index]:item.optBoolean("ready")?"READY · tap to use":item.optBoolean("special")?"Charging  "+(item.optInt("progress")*100/54)+"%":item.optBoolean("held")?"ON HOLD · tap to resume":item.optBoolean("producing")?"Building  "+(item.optInt("progress")*100/54)+"%":item.optBoolean("busy")?"Production busy":"$ "+item.optInt("cost");
            text(canvas,fit(sub,r.width()-24,18),r.left+12,r.top+(item==null?82:144),18,0xffadc4ca,false);
            if (item!=null && (item.optBoolean("producing") || item.optBoolean("special"))) {
                box(canvas,new RectF(r.left+126,r.top+62,r.right-12,r.top+72),0xff101e24);
                box(canvas,new RectF(r.left+126,r.top+62,r.left+126+(r.width()-138)*item.optInt("progress")/54f,r.top+72),0xffd9bc77);
            }
        }
        if (!data.optBoolean("active")) {
            box(canvas,new RectF(400,210,1210,940),0xff0c171c);
            text(canvas,"READY WHEN YOU ARE",440,330,32,0xffe2d2a8,true);
            text(canvas,"Choose a campaign or skirmish on the top screen.",440,395,24,0xffc0d0d3,false);
            text(canvas,"Left stick moves the cursor in menus. A clicks.",440,449,23,0xff9cb6be,false);
            text(canvas,"D-pad jumps between native menu buttons.",440,493,23,0xff9cb6be,false);
            text(canvas,"Original campaigns + Counterstrike + Aftermath",440,590,22,0xffd6b87c,false);
            if (data.optBoolean("mainMenu")) {
                box(canvas,new RectF(440,660,920,750),0xff71312b);
                text(canvas,"PLAY THE ANT MISSIONS",470,715,25,Color.WHITE,true);
            }
        } else if (total==0) {
            text(canvas,tab==2?"No powers available yet":"Nothing to produce yet",425,318,28,0xffb5c7cc,true);
            text(canvas,"Available choices follow the original game rules.",425,366,23,0xff829ea7,false);
        }
        text(canvas,"‹  PREVIOUS",409,977,21,0xffadbec4,true);
        text(canvas,"PAGE "+(page+1)+" / "+Math.max(1,(total+11)/12),720,977,21,0xffe4cf9c,true);
        text(canvas,"NEXT  ›",1060,977,21,0xffadbec4,true);
        text(canvas,radarMode?"MINIMAP MODE · touch or drag the radar to pan":"Build & Train: hold a tile to pause; hold again to cancel",28,1043,21,0xff8faab2,false);
        canvas.restore();
    }
    @Override public boolean onTouchEvent(MotionEvent e) {
        float x=e.getX()/Math.max(.01f,sx), y=e.getY()/Math.max(.01f,sy); int action=e.getActionMasked();
        if (action==MotionEvent.ACTION_DOWN) {
            owner.touch();
            held=-1; longPressed=false; startY=y; radarDrag=data.optBoolean("radar") && radarBounds().contains(x,y);
            if (data.optBoolean("mainMenu") && x>=440 && x<=920 && y>=660 && y<=750) { ThorActivity.command(15,0,0,0,0); return true; }
            if (y>=112 && y<=180) { tab=Math.max(0,Math.min(2,(int)((x-24)/405))); page=0; focus=-1; update(data,new int[0]); return true; }
            for (int i=0;i<hit.size();++i) if (hit.get(i).contains(x,y)) { held=page*12+i; final int index=held; handler.postDelayed(() -> { if (held==index && tab!=0) { longPressed=true; activate(index,true); } },600); }
            if (y>940) { if (x<650) navigate(-1,0); else if (x>1000) navigate(1,0); }
        }
        if ((action==MotionEvent.ACTION_DOWN || action==MotionEvent.ACTION_MOVE) && radarDrag) {
            RectF map=radarBounds();
            radarX=Math.max(0,Math.min(1,(x-map.left)/map.width()));
            radarY=Math.max(0,Math.min(1,(y-map.top)/map.height()));
            ThorActivity.command(6,0,0,radarX,radarY); return true;
        }
        if (action==MotionEvent.ACTION_UP || action==MotionEvent.ACTION_CANCEL) {
            handler.removeCallbacksAndMessages(null);
            if (action==MotionEvent.ACTION_UP && held>=0 && !longPressed && Math.abs(y-startY)<30) activate(held,false);
            held=-1; radarDrag=false; return true;
        }
        return true;
    }
}
