from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import random

# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════
WIN_W, WIN_H   = 1000, 800
GRID           = 600
DAY_DURATION   = 1200
NIGHT_DURATION = 900
BULLET_SPEED   = 20.0
BULLET_LIFE    = 90
BULLET_DAMAGE  = 2          # bullets hit harder (was 1)
SPAWN_INTERVAL = 60
POWERUP_LIFE   = 500
SUN_RADIUS     = 800
SUN_PEAK_Z     = 900

RAIN_WAVES     = {2, 4, 6, 8, 10}   # even waves have rain
NUM_RAIN_DROPS = 300

# ═══════════════════════════════════════════════════════════
#  GAME STATE
# ═══════════════════════════════════════════════════════════
game_state  = "MENU"          # MENU | DIFFICULTY | PLAYING | GAME_OVER
difficulty  = "NORMAL"        # EASY | NORMAL
menu_sel    = 0               # 0=Play, 1=Quit  (main menu)
diff_sel    = 0               # 0=Easy, 1=Normal

# Player
player_pos    = [0.0, -200.0, 20.0]
player_angle  = 0.0
player_speed  = 9.0
player_hp     = 5
player_max_hp = 5

# Controls
mouse_sensitivity = 0.25
first_person      = False
invincible        = False     # 'i' key cheat

# Camera (3rd-person orbit)
cam_angle_h = 0.0
cam_angle_v = 40.0
cam_radius  = 900.0

# Bullets / walls / enemies
bullets   = []
walls     = []
enemies   = []
base_hp   = 10
base_max  = 10
boss_proj = []

# Wave
wave             = 1
wave_phase       = "DAY"
phase_timer      = 0
enemies_to_spawn = 0
spawn_timer      = 0

# Score / resources
score = 0
wood  = 5
kills = 0
wall_cap = 5          # starts at 5; building powerup raises this

# Power-ups  [x, y, kind, age]
powerups = []

# Speed-boost
speed_boost_timer = 0
speed_boost_dur   = 0    # random 100-300 frames, set on pickup

# Rain
rain_drops = []   # [x, y, z, speed]

# Sky
sky_day   = (0.45, 0.70, 1.00)
sky_night = (0.02, 0.02, 0.10)
sky_dusk  = (0.80, 0.35, 0.10)
sky_rain  = (0.30, 0.35, 0.40)

# ═══════════════════════════════════════════════════════════
#  WAVE SPAWN TABLE
# ═══════════════════════════════════════════════════════════
def wave_spawn_count(w):
    if w % 3 == 0: return 2
    return 3 + (w - 1)

def wave_spawn_kind(w, remaining):
    if w % 3 == 0 and remaining == 1:
        return 'boss2' if w >= 6 else 'boss1'
    r = random.random()
    if w < 3:   return 'normal'
    elif w < 5: return 'fast' if r < 0.3 else 'normal'
    else:
        if r < 0.15: return 'tank'
        if r < 0.35: return 'fast'
        return 'normal'

# ═══════════════════════════════════════════════════════════
#  HUD TEXT HELPER
# ═══════════════════════════════════════════════════════════
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1,1,1)):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix(); glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix(); glLoadIdentity()
    glColor3f(*color)
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

# ═══════════════════════════════════════════════════════════
#  SOLID CUBOID  (w×d footprint, height h, base at z=0)
# ═══════════════════════════════════════════════════════════
def solid_cuboid(w, d, h):
    hw, hd = w/2, d/2
    glBegin(GL_QUADS)
    glNormal3f(0,0,-1)
    glVertex3f(-hw,-hd,0); glVertex3f(hw,-hd,0); glVertex3f(hw,hd,0); glVertex3f(-hw,hd,0)
    glNormal3f(0,0,1)
    glVertex3f(-hw,-hd,h); glVertex3f(-hw,hd,h); glVertex3f(hw,hd,h); glVertex3f(hw,-hd,h)
    glNormal3f(0,-1,0)
    glVertex3f(-hw,-hd,0); glVertex3f(-hw,-hd,h); glVertex3f(hw,-hd,h); glVertex3f(hw,-hd,0)
    glNormal3f(0,1,0)
    glVertex3f(-hw,hd,0); glVertex3f(hw,hd,0); glVertex3f(hw,hd,h); glVertex3f(-hw,hd,h)
    glNormal3f(-1,0,0)
    glVertex3f(-hw,-hd,0); glVertex3f(-hw,hd,0); glVertex3f(-hw,hd,h); glVertex3f(-hw,-hd,h)
    glNormal3f(1,0,0)
    glVertex3f(hw,-hd,0); glVertex3f(hw,-hd,h); glVertex3f(hw,hd,h); glVertex3f(hw,hd,0)
    glEnd()

# ═══════════════════════════════════════════════════════════
#  ENVIRONMENT
# ═══════════════════════════════════════════════════════════
def is_rain_wave():
    return wave in RAIN_WAVES

def sky_color():
    if is_rain_wave() and wave_phase == "NIGHT":
        return sky_rain
    if wave_phase == "DAY":
        t = phase_timer / DAY_DURATION
        if is_rain_wave():
            # Blend toward rainy sky
            base = tuple(sky_day[i]*0.6 + sky_rain[i]*0.4 for i in range(3))
        else:
            base = sky_day
        if t < 0.15:
            f = t/0.15
            return tuple(sky_dusk[i]*(1-f)+base[i]*f for i in range(3))
        elif t < 0.85:
            return base
        else:
            f = (t-0.85)/0.15
            return tuple(base[i]*(1-f)+sky_dusk[i]*f for i in range(3))
    else:
        t = min(phase_timer/60, 1.0)
        return tuple(sky_dusk[i]*(1-t)+sky_night[i]*t for i in range(3))

def init_rain():
    global rain_drops
    rain_drops = []
    for _ in range(NUM_RAIN_DROPS):
        rain_drops.append([
            random.uniform(-GRID, GRID),
            random.uniform(-GRID, GRID),
            random.uniform(50, 500),
            random.uniform(15, 25)
        ])

def update_rain():
    for d in rain_drops:
        d[2] -= d[3]
        if d[2] < 0:
            d[0] = random.uniform(-GRID, GRID)
            d[1] = random.uniform(-GRID, GRID)
            d[2] = random.uniform(400, 500)

def draw_rain():
    if not is_rain_wave(): return
    glColor3f(0.55, 0.65, 0.80)
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for d in rain_drops:
        glVertex3f(d[0], d[1], d[2])
        glVertex3f(d[0]-2, d[1]-2, d[2]-20)
    glEnd()
    glLineWidth(1.0)

def draw_floor():
    step = 40
    glBegin(GL_QUADS)
    for i in range(-GRID, GRID, step):
        for j in range(-GRID, GRID, step):
            if wave < 3:   c1,c2 = (0.20,0.45,0.15),(0.15,0.35,0.10)
            elif wave < 6: c1,c2 = (0.30,0.30,0.12),(0.22,0.22,0.08)
            else:          c1,c2 = (0.18,0.15,0.15),(0.12,0.10,0.10)
            if is_rain_wave():
                c1 = tuple(c*0.75 for c in c1)
                c2 = tuple(c*0.75 for c in c2)
            glColor3f(*(c1 if (i//step+j//step)%2==0 else c2))
            glVertex3f(i,j,0); glVertex3f(i+step,j,0)
            glVertex3f(i+step,j+step,0); glVertex3f(i,j+step,0)
    glEnd()

def draw_forest_boundary():
    """Dense forest — 40 trees around border + 20 inner scatter trees."""
    q = gluNewQuadric()

    # Border ring
    num_border = 40
    for k in range(num_border):
        ang  = 2*math.pi*k/num_border
        dist = GRID + random.Random(k).uniform(10, 50)
        rx   = dist*math.cos(ang)
        ry   = dist*math.sin(ang)
        _draw_tree(q, rx, ry, k)

    # Scattered inner-edge trees (seeded for consistency)
    rng = random.Random(42)
    for k in range(24):
        ang  = rng.uniform(0, 2*math.pi)
        dist = rng.uniform(GRID*0.82, GRID*0.95)
        rx   = dist*math.cos(ang)
        ry   = dist*math.sin(ang)
        _draw_tree(q, rx, ry, k+100)

def _draw_tree(q, rx, ry, seed):
    rng = random.Random(seed)
    trunk_h = rng.uniform(45, 75)
    scale   = rng.uniform(0.8, 1.3)
    glPushMatrix()
    glTranslatef(rx, ry, 0)
    glScalef(scale, scale, scale)
    glColor3f(0.35, 0.22, 0.10)
    gluCylinder(q, 8, 5, trunk_h, 8, 1)
    layers = [(30,38,trunk_h-10), (22,30,trunk_h+18), (14,24,trunk_h+36)]
    for layer, (r, h, z) in enumerate(layers):
        glPushMatrix()
        glTranslatef(0, 0, z)
        if wave < 3:   cr,cg,cb = 0.08+layer*0.04, 0.38-layer*0.05, 0.08
        elif wave < 6: cr,cg,cb = 0.42-layer*0.05, 0.28-layer*0.03, 0.04
        else:          cr,cg,cb = 0.18-layer*0.02, 0.07, 0.07
        if is_rain_wave():
            cr *= 0.7; cg *= 0.7; cb *= 0.7
        glColor3f(cr, cg, cb)
        gluCylinder(q, r, 0, h, 8, 1)
        glPopMatrix()
    glPopMatrix()

def draw_base():
    glPushMatrix()
    sides = 8; r_out = 55; h = 90
    glBegin(GL_QUADS)
    for k in range(sides):
        a1 = 2*math.pi*k/sides; a2 = 2*math.pi*(k+1)/sides
        ratio = base_hp/base_max
        glColor3f(0.45*(1-ratio)+0.4, 0.40*(1-ratio)+0.35, 0.30*(1-ratio)+0.25)
        x1,y1 = r_out*math.cos(a1), r_out*math.sin(a1)
        x2,y2 = r_out*math.cos(a2), r_out*math.sin(a2)
        glVertex3f(x1,y1,0); glVertex3f(x2,y2,0)
        glVertex3f(x2,y2,h); glVertex3f(x1,y1,h)
    glEnd()
    # Battlements
    for k in range(sides):
        a = 2*math.pi*(k+0.5)/sides
        glPushMatrix()
        glTranslatef(r_out*math.cos(a), r_out*math.sin(a), h)
        glColor3f(0.50,0.45,0.35); solid_cuboid(14,14,22)
        glPopMatrix()
    # Flag
    glPushMatrix()
    glTranslatef(0,0,h)
    glColor3f(0.55,0.55,0.55)
    gluCylinder(gluNewQuadric(),3,2,45,6,1)
    glTranslatef(0,0,45)
    glColor3f(0.9,0.15,0.15); solid_cuboid(28,3,16)
    glPopMatrix()
    # Easy mode outer wall ring
    if difficulty == "EASY":
        glColor3f(0.35, 0.50, 0.30)
        segs = 12; rw = 90
        for k in range(segs):
            a1 = 2*math.pi*k/segs; a2 = 2*math.pi*(k+1)/segs
            x1,y1 = rw*math.cos(a1), rw*math.sin(a1)
            x2,y2 = rw*math.cos(a2), rw*math.sin(a2)
            glPushMatrix()
            mx = (x1+x2)/2; my = (y1+y2)/2
            ang_seg = math.degrees(math.atan2(y2-y1, x2-x1))
            glTranslatef(mx, my, 0)
            glRotatef(ang_seg, 0, 0, 1)
            solid_cuboid(40, 10, 55)
            glPopMatrix()
    glPopMatrix()

def draw_sun_moon():
    dur = DAY_DURATION if wave_phase=="DAY" else NIGHT_DURATION
    t   = phase_timer/dur
    ang = math.pi*t
    sx  = SUN_RADIUS*(t-0.5)
    sz  = SUN_PEAK_Z*math.sin(ang)
    # Only draw when the sphere is fully above the ground
    if wave_phase == "DAY":
        if sz < 65: return   # sun radius 60 + buffer
    else:
        if sz < 42: return   # moon radius 38 + buffer
    glPushMatrix()
    glTranslatef(sx, -GRID*0.8, sz)
    if wave_phase == "DAY":
        glColor3f(1.0,0.95,0.60); gluSphere(gluNewQuadric(),60,16,16)
        q_w=gluNewQuadric(); gluQuadricDrawStyle(q_w,GLU_LINE)
        glColor3f(1.0,0.90,0.50); gluSphere(q_w,75,10,10)
    else:
        glColor3f(0.88,0.88,0.76); gluSphere(gluNewQuadric(),38,16,16)
    glPopMatrix()

# ═══════════════════════════════════════════════════════════
#  PLAYER — black tactical suit + machine gun
# ═══════════════════════════════════════════════════════════
def draw_player():
    glPushMatrix()
    glTranslatef(player_pos[0], player_pos[1], 0)
    glRotatef(player_angle, 0,0,1)
    if game_state == "GAME_OVER":
        glRotatef(90,1,0,0)

    q = gluNewQuadric()

    # Invincible glow ring
    if invincible:
        glColor3f(0.8,0.8,0.0)
        q_w=gluNewQuadric(); gluQuadricDrawStyle(q_w,GLU_LINE); gluSphere(q_w,45,12,12)

    # Boots
    for sx in (-9,9):
        glPushMatrix(); glTranslatef(sx,2,0)
        glColor3f(0.10,0.10,0.12); solid_cuboid(12,14,8)
        glPopMatrix()
    # Legs
    for sx in (-9,9):
        glPushMatrix(); glTranslatef(sx,0,8)
        glColor3f(0.08,0.08,0.10); gluCylinder(q,6,5,22,8,1)
        glTranslatef(0,-5,10); glColor3f(0.0,0.85,1.0); solid_cuboid(10,4,5)
        glPopMatrix()
    # Hips
    glPushMatrix(); glTranslatef(0,0,29)
    glColor3f(0.15,0.15,0.18); glScalef(1.0,0.55,0.35); glutSolidCube(32)
    glPopMatrix()
    # Torso
    glPushMatrix(); glTranslatef(0,0,34)
    glColor3f(0.10,0.10,0.12); glScalef(1.05,0.58,1.1); glutSolidCube(34)
    glColor3f(0.0,0.85,1.0)
    for zoff in (6,14):
        glPushMatrix(); glTranslatef(0,-11,zoff-17); solid_cuboid(30,2,2); glPopMatrix()
    glPopMatrix()
    # Shoulders
    for sx in (-20,20):
        glPushMatrix(); glTranslatef(sx,0,48)
        glColor3f(0.12,0.12,0.14); gluSphere(gluNewQuadric(),10,8,8)
        glColor3f(0.0,0.85,1.0); q_w=gluNewQuadric(); gluQuadricDrawStyle(q_w,GLU_LINE); gluSphere(q_w,10.5,6,6)
        glPopMatrix()
    # Arms
    for sx in (-20,20):
        glPushMatrix(); glTranslatef(sx,0,42)
        glColor3f(0.10,0.10,0.12); gluCylinder(q,5,4,18,8,1)
        glPopMatrix()
    # Gloves
    for sx in (-20,20):
        glPushMatrix(); glTranslatef(sx,0,42)
        glColor3f(0.05,0.05,0.06); solid_cuboid(10,10,8)
        glPopMatrix()
    # Helmet
    glPushMatrix(); glTranslatef(0,0,60)
    glColor3f(0.10,0.10,0.12); gluSphere(gluNewQuadric(),14,12,12)
    glTranslatef(0,-12,-2); glColor3f(1.0,0.45,0.0)
    glScalef(1.1,0.25,0.55); glutSolidCube(18)
    glPopMatrix()
    # Machine gun
    glPushMatrix(); glTranslatef(15,-8,44); glRotatef(90,1,0,0)
    glColor3f(0.12,0.12,0.12); gluCylinder(q,5,4,65,10,1)
    glColor3f(0.18,0.18,0.18); gluCylinder(q,7,7,30,10,1)
    glTranslatef(0,0,65); glColor3f(0.08,0.08,0.08); gluCylinder(q,4,6,10,8,1)
    glPopMatrix()
    glPushMatrix(); glTranslatef(15,-4,38)
    glColor3f(0.20,0.20,0.20); solid_cuboid(8,6,14); glPopMatrix()
    glPushMatrix(); glTranslatef(15,-14,48)
    glColor3f(0.25,0.25,0.25); solid_cuboid(8,4,6); glPopMatrix()

    glPopMatrix()

# ═══════════════════════════════════════════════════════════
#  ENEMIES
# ═══════════════════════════════════════════════════════════
KIND_SCALE = {'normal':1.0,'fast':0.62,'tank':1.60,'boss1':2.0,'boss2':2.75}
KIND_HP    = {'normal':2,  'fast':1,   'tank':5,   'boss1':15, 'boss2':28}  # reduced HP
KIND_SPD   = {'normal':0.65,'fast':1.5,'tank':0.38,'boss1':0.45,'boss2':0.40}
KIND_PTS   = {'normal':10, 'fast':15,  'tank':20,  'boss1':100,'boss2':200}
KIND_SKIN  = {
    'normal':(0.35,0.55,0.22),'fast':(0.65,0.80,0.18),
    'tank':(0.18,0.32,0.12), 'boss1':(0.58,0.10,0.58),'boss2':(0.75,0.05,0.05),
}

def spawn_zombie(kind='normal'):
    ang  = random.uniform(0,2*math.pi)
    dist = GRID*random.uniform(0.88,0.96)
    hp = KIND_HP[kind]
    if difficulty == "EASY": hp = max(1, hp - 1)
    enemies.append({
        'x':dist*math.cos(ang),'y':dist*math.sin(ang),'z':0,
        'hp':hp,'max_hp':hp,
        'speed':KIND_SPD[kind],'kind':kind,
        'anim':random.uniform(0,2*math.pi),'atk_timer':0,
    })

def draw_zombie(e):
    q=gluNewQuadric(); kind=e['kind']; anim=e['anim']
    sc=KIND_SCALE[kind]; skin=KIND_SKIN[kind]; cloth=(0.16,0.11,0.07)
    glPushMatrix()
    glTranslatef(e['x'],e['y'],e['z'])
    dx=player_pos[0]-e['x']; dy=player_pos[1]-e['y']
    glRotatef(math.degrees(math.atan2(dy,dx))-90,0,0,1)
    glScalef(sc,sc,sc)
    swing=18*math.sin(anim)
    # Legs
    for side,lsw in ((-7,swing),(7,-swing)):
        glPushMatrix(); glTranslatef(side,0,0); glRotatef(lsw,1,0,0)
        glColor3f(*cloth); gluCylinder(q,4.5,3.5,27,7,1)
        glTranslatef(0,0,-4); glColor3f(0.12,0.08,0.05); solid_cuboid(9,12,6)
        glPopMatrix()
    # Torso
    glPushMatrix(); glTranslatef(0,0,27); glRotatef(-30,1,0,0)
    glColor3f(*skin); glScalef(0.95,0.50,1.05); glutSolidCube(30)
    glColor3f(skin[0]*0.6,skin[1]*0.6,skin[2]*0.6)
    for rib in range(3):
        glPushMatrix(); glTranslatef(0,-9,rib*6-4); solid_cuboid(24,3,3); glPopMatrix()
    for side,asw in ((-16,-swing*0.6-20),(16,swing*0.6-20)):
        glPushMatrix(); glTranslatef(side,0,6); glRotatef(asw,1,0,0)
        glColor3f(*skin); gluCylinder(q,4,2.5,30,7,1)
        glTranslatef(0,0,30); glColor3f(0.15,0.12,0.10)
        for c in range(3):
            glPushMatrix(); glRotatef((c-1)*25,0,1,0); gluCylinder(q,1.5,0.2,10,5,1); glPopMatrix()
        glPopMatrix()
    glPushMatrix(); glTranslatef(0,0,30)
    glColor3f(*skin); gluCylinder(q,5,4,10,8,1)
    glTranslatef(0,0,10); gluSphere(gluNewQuadric(),13,10,10)
    eye_col=(1.0,0.3,0.0) if kind in ('boss1','boss2') else (0.7,1.0,0.1)
    for ex in (-5,5):
        glPushMatrix(); glTranslatef(ex,-11,1); glColor3f(*eye_col); gluSphere(gluNewQuadric(),2.8,6,6); glPopMatrix()
    if kind in ('boss1','boss2'):
        for hx in (-9,9):
            glPushMatrix(); glTranslatef(hx,0,10); glColor3f(0.12,0.04,0.04); gluCylinder(q,3.5,0.4,20,6,1); glPopMatrix()
    if kind=='boss2':
        glTranslatef(0,-11,-2); glColor3f(0.85,0.85,0.75); glScalef(0.9,0.2,0.7); glutSolidCube(18)
    glPopMatrix(); glPopMatrix()
    glPopMatrix()
    _draw_hp_bar(e['x'],e['y'],e['z']+90*sc,e['hp'],e['max_hp'])

def _draw_hp_bar(x,y,z,hp,max_hp):
    ratio=max(0,hp/max_hp)
    glPushMatrix(); glTranslatef(x,y,z)
    glBegin(GL_QUADS)
    glColor3f(0.55,0.0,0.0)
    glVertex3f(-22,-1,0); glVertex3f(22,-1,0); glVertex3f(22,1,0); glVertex3f(-22,1,0)
    glColor3f(0.05,0.9,0.15)
    glVertex3f(-22,-1,0); glVertex3f(-22+44*ratio,-1,0); glVertex3f(-22+44*ratio,1,0); glVertex3f(-22,1,0)
    glEnd()
    glPopMatrix()

# ═══════════════════════════════════════════════════════════
#  MEAT BARRICADES — sturdier (hp=8) and longer (100 wide)
# ═══════════════════════════════════════════════════════════
WALL_HP  = 8
WALL_W   = 100   # was 80

def draw_walls():
    for w in walls:
        glPushMatrix()
        glTranslatef(w[0],w[1],0); glRotatef(w[2],0,0,1)
        ratio = w[3]/WALL_HP
        # Small meat cube — reddish pink, darkens as HP drops
        glColor3f(0.75*ratio+0.15, 0.20*ratio+0.08, 0.15*ratio+0.05)
        solid_cuboid(30,30,30)
        # Fat/marbling streak
        glColor3f(0.90,0.80,0.55)
        glPushMatrix(); glTranslatef(0,-16,15); solid_cuboid(28,2,3); glPopMatrix()
        glPopMatrix()

# ═══════════════════════════════════════════════════════════
#  POWER-UPS   kinds: 'health' | 'speed' | 'build'
# ═══════════════════════════════════════════════════════════
def draw_powerups():
    for p in powerups:
        glPushMatrix()
        glTranslatef(p[0],p[1],22)
        glRotatef((p[3]%360)*2,0,0,1)
        if p[2]=='health':
            glColor3f(0.9,0.1,0.3)
            solid_cuboid(6,24,9); solid_cuboid(24,6,9)
        elif p[2]=='speed':
            glColor3f(0.1,0.6,1.0); gluSphere(gluNewQuadric(),12,12,12)
            glColor3f(1.0,1.0,0.2); glTranslatef(0,0,12)
            gluCylinder(gluNewQuadric(),6,0,14,8,1)
        elif p[2]=='build':
            # Yellow crate icon
            glColor3f(0.9,0.75,0.1); solid_cuboid(20,20,20)
            glColor3f(0.5,0.35,0.0)
            solid_cuboid(20,3,3); solid_cuboid(3,20,3)
            glTranslatef(0,0,17); solid_cuboid(20,3,3); solid_cuboid(3,20,3)
        glPopMatrix()

def spawn_wave_powerups():
    """Spawn 2-3 random powerups at the start of each day phase."""
    count = random.randint(2,3)
    kinds = ['health','speed','build']
    for _ in range(count):
        x = random.uniform(-GRID*0.65, GRID*0.65)
        y = random.uniform(-GRID*0.65, GRID*0.65)
        # Keep away from base
        while math.sqrt(x*x+y*y) < 120:
            x = random.uniform(-GRID*0.65, GRID*0.65)
            y = random.uniform(-GRID*0.65, GRID*0.65)
        powerups.append([x, y, random.choice(kinds), 0])

# ═══════════════════════════════════════════════════════════
#  BULLETS
# ═══════════════════════════════════════════════════════════
def draw_bullets():
    for b in bullets:
        glPushMatrix(); glTranslatef(b[0],b[1],b[2])
        glColor3f(1.0,0.85,0.10); gluSphere(gluNewQuadric(),4,8,8)
        glColor3f(1.0,0.40,0.05)
        glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(-b[3]*3,-b[4]*3,0); glEnd()
        glPopMatrix()

def draw_boss_proj():
    for p in boss_proj:
        glPushMatrix(); glTranslatef(p[0],p[1],p[2])
        glColor3f(1.0,0.20,0.80); gluSphere(gluNewQuadric(),8,8,8)
        glPopMatrix()

# ═══════════════════════════════════════════════════════════
#  HUD
# ═══════════════════════════════════════════════════════════
def draw_hud():
    glDisable(GL_DEPTH_TEST)
    mode_tag = "[EASY]" if difficulty=="EASY" else "[NORMAL]"
    draw_text(12,WIN_H-26, f"Wave {wave} {mode_tag}  [{wave_phase}]",    color=(1.0,0.9,0.3))
    draw_text(12,WIN_H-50, f"Base HP: {base_hp}/{base_max}",             color=(0.4,0.9,1.0))
    draw_text(12,WIN_H-74, f"Player HP: {player_hp}/{player_max_hp}",    color=(0.3,1.0,0.4))
    draw_text(12,WIN_H-98, f"Score: {score}",                            color=(1.0,1.0,1.0))
    draw_text(12,WIN_H-122,f"Meat: {len(walls)}/{wall_cap}  (budget: {wood})", color=(0.9,0.6,0.2))
    if invincible:
        draw_text(12,WIN_H-146,"[INVINCIBLE CHEAT ON]",                  color=(1.0,1.0,0.0))
    if speed_boost_timer>0:
        draw_text(12,WIN_H-170,f"SPEED BOOST {speed_boost_timer//60+1}s",color=(0.2,0.7,1.0))
    if is_rain_wave():
        draw_text(WIN_W-130,WIN_H-26,"[ RAIN ]",                         color=(0.5,0.7,1.0))

    dur=DAY_DURATION if wave_phase=="DAY" else NIGHT_DURATION
    rem=max(0,dur-phase_timer)
    if wave_phase=="DAY":
        draw_text(WIN_W//2-100,WIN_H-26,f"Night in: {rem//60+1}s",      color=(1.0,0.7,0.2))
        draw_text(WIN_W//2-100,WIN_H-50,"Fortify & grab pickups!",       color=(0.8,0.5,0.1))
    else:
        draw_text(WIN_W//2-100,WIN_H-26,f"Enemies left: {enemies_to_spawn+len(enemies)}", color=(1.0,0.3,0.3))

    cam_hint = "Mouse:aim  C:3rd-person" if first_person else "Arrows:orbit  C:1st-person(mouse aim)"
    draw_text(12,14,f"WS:fwd/back  AD:turn  LClick:shoot  E:wall  I:invincible  {cam_hint}",
              font=GLUT_BITMAP_HELVETICA_12,color=(0.6,0.6,0.6))

    if first_person:
        draw_text(WIN_W//2-4,WIN_H//2-8,"+",color=(0.0,1.0,0.4))

    glEnable(GL_DEPTH_TEST)

# ─────────────── MENU SCREENS ───────────────
def draw_main_menu():
    glDisable(GL_DEPTH_TEST)
    draw_text(WIN_W//2-210,WIN_H//2+110,"NIGHTFALL: UNDEAD SIEGE",
              font=GLUT_BITMAP_TIMES_ROMAN_24,color=(0.9,0.15,0.1))
    draw_text(WIN_W//2-140,WIN_H//2+65,"Defend the tower. Survive the night.",
              color=(0.85,0.75,0.55))

    opts = ["  Play Game","  Quit"]
    for i,opt in enumerate(opts):
        col = (0.3,1.0,0.4) if i==menu_sel else (0.75,0.75,0.75)
        draw_text(WIN_W//2-100, WIN_H//2+10-i*40, opt,
                  font=GLUT_BITMAP_TIMES_ROMAN_24, color=col)

    draw_text(WIN_W//2-160,WIN_H//2-90,"UP/DOWN to select,  ENTER to confirm",
              font=GLUT_BITMAP_HELVETICA_12,color=(0.5,0.5,0.5))
    glEnable(GL_DEPTH_TEST)

def draw_difficulty_menu():
    glDisable(GL_DEPTH_TEST)
    draw_text(WIN_W//2-140,WIN_H//2+80,"Select Difficulty",
              font=GLUT_BITMAP_TIMES_ROMAN_24,color=(1.0,0.85,0.2))

    descs = [
        ("  Easy",   "Extra base walls, weaker enemies, same powerups"),
        ("  Normal", "Standard challenge — no extra defences"),
    ]
    for i,(label,desc) in enumerate(descs):
        col = (0.3,1.0,0.4) if i==diff_sel else (0.75,0.75,0.75)
        draw_text(WIN_W//2-140, WIN_H//2+20-i*55, label,
                  font=GLUT_BITMAP_TIMES_ROMAN_24, color=col)
        draw_text(WIN_W//2-140, WIN_H//2+0-i*55, desc,
                  font=GLUT_BITMAP_HELVETICA_12, color=(0.6,0.6,0.6))

    draw_text(WIN_W//2-160,WIN_H//2-110,"UP/DOWN to select,  ENTER to confirm",
              font=GLUT_BITMAP_HELVETICA_12,color=(0.5,0.5,0.5))
    glEnable(GL_DEPTH_TEST)

def draw_game_over_screen():
    glDisable(GL_DEPTH_TEST)
    draw_text(WIN_W//2-130,WIN_H//2+60,"GAME OVER",
              font=GLUT_BITMAP_TIMES_ROMAN_24,color=(1.0,0.1,0.1))
    draw_text(WIN_W//2-130,WIN_H//2+10,f"Final Score: {score}",color=(1.0,0.9,0.3))
    draw_text(WIN_W//2-130,WIN_H//2-30,f"Wave reached: {wave}",color=(0.6,0.8,1.0))
    draw_text(WIN_W//2-130,WIN_H//2-70,"R : restart    M : main menu",color=(0.8,0.8,0.8))
    glEnable(GL_DEPTH_TEST)

# ═══════════════════════════════════════════════════════════
#  CAMERA
# ═══════════════════════════════════════════════════════════
def setup_camera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(70,WIN_W/WIN_H,1,3500)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()

    if first_person:
        rad=math.radians(player_angle-90)
        ex=player_pos[0]+15*math.cos(rad); ey=player_pos[1]+15*math.sin(rad); ez=62
        gluLookAt(ex,ey,ez, ex+300*math.cos(rad),ey+300*math.sin(rad),ez, 0,0,1)
    else:
        rh=math.radians(cam_angle_h); rv=math.radians(cam_angle_v)
        cx=cam_radius*math.cos(rh)*math.cos(rv)
        cy=cam_radius*math.sin(rh)*math.cos(rv)
        cz=cam_radius*math.sin(rv)
        gluLookAt(cx,cy,cz,0,0,0,0,0,1)

# ═══════════════════════════════════════════════════════════
#  ACTIONS
# ═══════════════════════════════════════════════════════════
def fire_bullet():
    rad=math.radians(player_angle-90)
    bx=player_pos[0]+50*math.cos(rad); by=player_pos[1]+50*math.sin(rad)
    bullets.append([bx,by,35, BULLET_SPEED*math.cos(rad),BULLET_SPEED*math.sin(rad),0])

def place_wall():
    global wood
    if wood<=0 or len(walls)>=wall_cap: return
    rad=math.radians(player_angle-90)
    walls.append([player_pos[0]+80*math.cos(rad),player_pos[1]+80*math.sin(rad),
                  player_angle, WALL_HP])
    wood-=1

def _clamp_player():
    player_pos[0]=max(-GRID+20,min(GRID-20,player_pos[0]))
    player_pos[1]=max(-GRID+20,min(GRID-20,player_pos[1]))
    # Prevent entering the tower
    dist=math.sqrt(player_pos[0]**2+player_pos[1]**2)
    if dist<75 and dist>0:
        factor=75/dist
        player_pos[0]*=factor; player_pos[1]*=factor

def advance_wave():
    global wave,wave_phase,phase_timer,enemies_to_spawn,score,wood
    wave+=1; wave_phase="DAY"; phase_timer=0
    score+=wave*10; wood=min(wood+2,wall_cap)
    if is_rain_wave(): init_rain()
    spawn_wave_powerups()

def reset_game():
    global player_pos,player_angle,player_hp,player_speed
    global bullets,walls,enemies,powerups,boss_proj
    global wave,wave_phase,phase_timer,enemies_to_spawn,spawn_timer
    global score,wood,kills,base_hp,speed_boost_timer,speed_boost_dur
    global game_state,first_person,invincible,wall_cap,rain_drops

    player_pos=[0.0,-200.0,20.0]; player_angle=0.0
    player_hp=5; player_speed=9.0
    bullets=[]; walls=[]; enemies=[]; powerups=[]; boss_proj=[]
    wave=1; wave_phase="DAY"; phase_timer=0
    enemies_to_spawn=0; spawn_timer=0
    score=0; wood=5; kills=0; base_hp=10
    speed_boost_timer=0; speed_boost_dur=0
    first_person=False; invincible=False; wall_cap=5
    rain_drops=[]
    game_state="PLAYING"
    spawn_wave_powerups()   # first day pickups

# ═══════════════════════════════════════════════════════════
#  GAME LOGIC
# ═══════════════════════════════════════════════════════════
def _find_target(e):
    best_d=float('inf'); best_w=None
    for w in walls:
        d=math.sqrt((w[0]-e['x'])**2+(w[1]-e['y'])**2)
        if d<best_d: best_d=d; best_w=w
    if best_w and best_d<200: return best_w[0],best_w[1]
    if math.sqrt((player_pos[0]-e['x'])**2+(player_pos[1]-e['y'])**2)<350:
        return player_pos[0],player_pos[1]
    return 0.0,0.0

def game_logic():
    global phase_timer,wave_phase,enemies_to_spawn,spawn_timer
    global player_hp,base_hp,score,kills,wood
    global speed_boost_timer,speed_boost_dur,game_state,wall_cap

    if game_state!="PLAYING": return

    # ── Rain ──
    if is_rain_wave(): update_rain()

    # ── Day/Night ──
    phase_timer+=1
    if wave_phase=="DAY":
        if phase_timer>=DAY_DURATION:
            wave_phase="NIGHT"; phase_timer=0
            enemies_to_spawn=wave_spawn_count(wave)
    else:
        spawn_timer+=1
        if spawn_timer>=SPAWN_INTERVAL and enemies_to_spawn>0:
            spawn_timer=0
            kind=wave_spawn_kind(wave,enemies_to_spawn)
            spawn_zombie(kind); enemies_to_spawn-=1
        if phase_timer>=NIGHT_DURATION and enemies_to_spawn==0 and len(enemies)==0:
            advance_wave()

    # ── Speed boost ──
    if speed_boost_timer>0:
        speed_boost_timer-=1; player_speed=16.0
    else:
        player_speed=9.0

    # ── Enemy anim & AI ──
    for e in enemies: e['anim']+=0.10

    for e in enemies[:]:
        tx,ty=_find_target(e)
        dx=tx-e['x']; dy=ty-e['y']; dist=math.sqrt(dx*dx+dy*dy)
        if dist>5:
            spd=e['speed']*(1+min(wave,8)*0.03)
            e['x']+=spd*dx/dist; e['y']+=spd*dy/dist
        e['atk_timer']+=1

        for w in walls[:]:
            wd=math.sqrt((w[0]-e['x'])**2+(w[1]-e['y'])**2)
            if wd<58 and e['atk_timer']>=70:
                w[3]-=1; e['atk_timer']=0
                if w[3]<=0: walls.remove(w)
                break

        pd=math.sqrt((player_pos[0]-e['x'])**2+(player_pos[1]-e['y'])**2)
        if pd<38 and e['atk_timer']>=80 and not invincible:
            player_hp-=1; e['atk_timer']=0
            if player_hp<=0: game_state="GAME_OVER"; return

        bd=math.sqrt(e['x']**2+e['y']**2)
        if bd<68 and e['atk_timer']>=100 and not invincible:
            base_hp-=1; e['atk_timer']=0
            if base_hp<=0: game_state="GAME_OVER"; return

        if e['kind']=='boss2' and e['atk_timer']%180==0:
            pdx2=player_pos[0]-e['x']; pdy2=player_pos[1]-e['y']
            pd2=math.sqrt(pdx2**2+pdy2**2)
            if pd2>0:
                s=7; boss_proj.append([e['x'],e['y'],40,s*pdx2/pd2,s*pdy2/pd2,0,0])

    # ── Boss projectiles ──
    for p in boss_proj[:]:
        p[0]+=p[3]; p[1]+=p[4]; p[6]+=1
        if math.sqrt((player_pos[0]-p[0])**2+(player_pos[1]-p[1])**2)<22 and not invincible:
            player_hp-=1; boss_proj.remove(p)
            if player_hp<=0: game_state="GAME_OVER"; return
            continue
        if p[6]>140: boss_proj.remove(p)

    # ── Bullets ──
    for b in bullets[:]:
        b[0]+=b[3]; b[1]+=b[4]; b[5]+=1
        if b[5]>BULLET_LIFE or abs(b[0])>GRID+50 or abs(b[1])>GRID+50:
            if b in bullets: bullets.remove(b)
            continue
        hit=False
        for e in enemies[:]:
            if math.sqrt((b[0]-e['x'])**2+(b[1]-e['y'])**2)<max(22*KIND_SCALE[e['kind']],18):
                e['hp']-=BULLET_DAMAGE
                if b in bullets: bullets.remove(b)
                hit=True
                if e['hp']<=0:
                    score+=KIND_PTS[e['kind']]; kills+=1
                    if kills%5==0: wood=min(wood+1,wall_cap)
                    enemies.remove(e)
                break
        if hit: continue

    # ── Power-ups ──
    for p in powerups[:]:
        p[3]+=1
        pdx=player_pos[0]-p[0]; pdy=player_pos[1]-p[1]
        if math.sqrt(pdx*pdx+pdy*pdy)<32:
            if p[2]=='health':
                player_hp=min(player_hp+2,player_max_hp)
            elif p[2]=='speed':
                speed_boost_dur=random.randint(100,300)
                speed_boost_timer=speed_boost_dur
            elif p[2]=='build':
                wall_cap=min(wall_cap+1,8)   # increments 5→6→7→8 then caps
                wood=min(wood+2,wall_cap)
            powerups.remove(p); continue
        if p[3]>POWERUP_LIFE: powerups.remove(p)

# ═══════════════════════════════════════════════════════════
#  DISPLAY
# ═══════════════════════════════════════════════════════════
def display():
    sc=sky_color()
    glClearColor(*sc,1.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    if game_state in ("MENU","DIFFICULTY"):
        setup_camera()
        draw_floor(); draw_forest_boundary(); draw_base()
        if game_state=="MENU":       draw_main_menu()
        else:                        draw_difficulty_menu()
    else:
        setup_camera()
        draw_sun_moon()
        draw_floor(); draw_forest_boundary(); draw_base()
        draw_walls()
        for e in enemies: draw_zombie(e)
        draw_player()
        draw_bullets(); draw_boss_proj(); draw_powerups()
        if is_rain_wave(): draw_rain()
        draw_hud()
        if game_state=="GAME_OVER": draw_game_over_screen()

    glutSwapBuffers()

# ═══════════════════════════════════════════════════════════
#  INPUT
# ═══════════════════════════════════════════════════════════
def keyboard(key,x,y):
    global player_angle,player_pos,first_person,game_state
    global menu_sel,diff_sel,difficulty,invincible

    # ── MAIN MENU ──
    if game_state=="MENU":
        if key==b'\r':
            if menu_sel==0: game_state="DIFFICULTY"
            else:           glutLeaveMainLoop()
        return

    # ── DIFFICULTY MENU ──
    if game_state=="DIFFICULTY":
        if key==b'\r':
            difficulty="EASY" if diff_sel==0 else "NORMAL"
            reset_game()
        return

    # ── GAME OVER ──
    if game_state=="GAME_OVER":
        if key==b'r' or key==b'R': reset_game()
        elif key==b'm' or key==b'M': game_state="MENU"; menu_sel=0
        return

    # ── PLAYING ──
    sp=player_speed
    if key==b'w':
        rad=math.radians(player_angle-90)
        player_pos[0]+=sp*math.cos(rad); player_pos[1]+=sp*math.sin(rad)
        _clamp_player()
    elif key==b's':
        rad=math.radians(player_angle-90)
        player_pos[0]-=sp*math.cos(rad); player_pos[1]-=sp*math.sin(rad)
        _clamp_player()
    elif key==b'a':
        if not first_person: player_angle+=5
    elif key==b'd':
        if not first_person: player_angle-=5
    elif key==b'e':
        place_wall()
    elif key==b'c':
        first_person=not first_person
        if first_person: glutWarpPointer(WIN_W//2,WIN_H//2)
    elif key==b'i':
        invincible=not invincible   # cheat: invincibility
    glutPostRedisplay()

def special_key(key,x,y):
    global cam_angle_h,cam_angle_v,menu_sel,diff_sel

    if game_state=="MENU":
        if key==GLUT_KEY_UP:   menu_sel=(menu_sel-1)%2
        elif key==GLUT_KEY_DOWN: menu_sel=(menu_sel+1)%2
        glutPostRedisplay(); return

    if game_state=="DIFFICULTY":
        if key==GLUT_KEY_UP:   diff_sel=(diff_sel-1)%2
        elif key==GLUT_KEY_DOWN: diff_sel=(diff_sel+1)%2
        glutPostRedisplay(); return

    if key==GLUT_KEY_LEFT:  cam_angle_h-=5
    elif key==GLUT_KEY_RIGHT: cam_angle_h+=5
    elif key==GLUT_KEY_UP:   cam_angle_v=min(89,cam_angle_v+3)
    elif key==GLUT_KEY_DOWN: cam_angle_v=max(5, cam_angle_v-3)
    glutPostRedisplay()

def mouse_click(button,state,x,y):
    if game_state=="PLAYING" and button==GLUT_LEFT_BUTTON and state==GLUT_DOWN:
        fire_bullet()
    glutPostRedisplay()

def mouse_motion(mx,my):
    global player_angle
    if game_state!="PLAYING" or not first_person: return
    dx=mx-WIN_W//2
    if dx!=0:
        player_angle-=dx*mouse_sensitivity
        glutWarpPointer(WIN_W//2,WIN_H//2)
    glutPostRedisplay()

# Fixed timestep — runs game_logic at ~60fps regardless of monitor refresh rate
TARGET_FPS  = 60
FRAME_TIME  = 1000 // TARGET_FPS    # ~16 ms
last_frame_time = 0

def idle():
    global last_frame_time
    current_time = glutGet(GLUT_ELAPSED_TIME)
    if current_time - last_frame_time >= FRAME_TIME:
        last_frame_time = current_time
        game_logic()
        glutPostRedisplay()

# ═══════════════════════════════════════════════════════════
#  INIT & MAIN
# ═══════════════════════════════════════════════════════════
def init():
    glEnable(GL_DEPTH_TEST)


def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(WIN_W,WIN_H)
    glutInitWindowPosition(80,50)
    glutCreateWindow(b"Nightfall: Undead Siege")
    init()
    glutDisplayFunc(display)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special_key)
    glutMouseFunc(mouse_click)
    glutPassiveMotionFunc(mouse_motion)
    glutMainLoop()

if __name__=="__main__":
    main()
