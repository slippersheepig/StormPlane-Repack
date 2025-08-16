from js import document, window, console, Math
from pyodide.ffi import create_proxy
from utils import rects_collide, clamp, randf, load_sprite

# Lazily ensure canvas exists and return (canvas, ctx)
def ensure_canvas_and_ctx():
    canvas = document.getElementById("game-canvas")
    if canvas is None:
        # 如果缺失，尝试把 canvas 插入到 #game-container 中，若没有 container 再插到 body
        container = document.getElementById("game-container")
        if container is None:
            container = document.body
            console.warn("ensure_canvas_and_ctx: #game-container missing, appending canvas to <body>.")
        canvas = document.createElement("canvas")
        canvas.id = "game-canvas"
        canvas.style.display = "block"
        container.appendChild(canvas)
        console.warn("ensure_canvas_and_ctx: created missing #game-canvas element.")
    try:
        ctx = canvas.getContext("2d")
    except Exception as e:
        console.warn("ensure_canvas_and_ctx: getContext failed: " + str(e))
        ctx = None
    return canvas, ctx

# initialize global references (may create canvas if missing)
canvas, ctx = ensure_canvas_and_ctx()

def fit_canvas():
    container = document.getElementById("game-container")
    if container is not None:
        try:
            rect = container.getBoundingClientRect()
            w = rect.width
            h = rect.height
        except Exception as e:
            console.warn("fit_canvas: getBoundingClientRect failed: " + str(e))
            w = window.innerWidth or document.documentElement.clientWidth or 0
            h = window.innerHeight or document.documentElement.clientHeight or 0
    else:
        # Fallback: entire viewport
        w = window.innerWidth or document.documentElement.clientWidth or 0
        h = window.innerHeight or document.documentElement.clientHeight or 0

    try:
        dpr = window.devicePixelRatio or 1
    except Exception:
        dpr = 1

    if ctx:
        try:
            canvas.style.width = str(w) + "px"
            canvas.style.height = str(h) + "px"
            canvas.width = int(Math.floor(w))
            canvas.height = int(Math.floor(h))
        except Exception:
            pass
        try:
            ctx.setTransform(1, 0, 0, 1, 0, 0)
        except Exception:
            pass

    try:
        if "player" in globals() and player is not None:
            player.x = clamp(player.x, 0, canvas.width - player.w)
            player.y = clamp(player.y, 0, canvas.height - player.h)
        if "bullets" in globals() and bullets is not None:
            for b in list(bullets):
                try:
                    b.x = clamp(b.x, -200, canvas.width + 200)
                    b.y = clamp(b.y, -200, canvas.height + 200)
                except Exception:
                    continue
        if "powers" in globals() and powers is not None:
            for p in list(powers):
                try:
                    p.x = clamp(p.x, -200, canvas.width + 200)
                    p.y = clamp(p.y, -200, canvas.height + 200)
                except Exception:
                    continue
    except Exception:
        pass

# Run initial fit and register resize + DOMContentLoaded hooks
fit_canvas()
window.addEventListener("resize", create_proxy(lambda e: fit_canvas()))
document.addEventListener("DOMContentLoaded", create_proxy(lambda e: fit_canvas()), {"once": True})
try:
    fit_canvas()
except Exception:
    pass

# HUD elements
hud = document.getElementById("hud")
score_el = document.getElementById("score")
lives_el = document.getElementById("lives")
level_el = document.getElementById("level")

# Menu elements
menu = document.getElementById("menu")
start_btn = document.getElementById("start-btn")
diff_buttons = menu.querySelectorAll(".btns button")
selected_diff = "normal"
for i in range(diff_buttons.length):
    b = diff_buttons.item(i)
    def on_diff(evt, btn=b):
        global selected_diff
        # 切换选中状态
        for k in range(diff_buttons.length):
            diff_buttons.item(k).classList.remove("active")
        btn.classList.add("active")
        selected_diff = btn.getAttribute("data-diff")
    b.addEventListener("click", create_proxy(on_diff))
# 预先设定普通难度为默认
diff_buttons.item(1).classList.add("active")  # normal default

game_over = False
state = "menu"  # 'menu' -> 'playing' -> 'gameover'

# Difficulty settings
DIFF = {
    "easy":   {"enemy_rate": 0.015, "enemy_speed": (1.0,2.0), "bullet_rate": 0.004, "boss_hp": 1200},
    "normal": {"enemy_rate": 0.022, "enemy_speed": (1.8,2.8), "bullet_rate": 0.008, "boss_hp": 1800},
    "hard":   {"enemy_rate": 0.03,  "enemy_speed": (2.6,3.6), "bullet_rate": 0.012, "boss_hp": 2400},
}
DIFF_NAME_ZH = {"easy": "简单", "normal": "普通", "hard": "困难"}

IMG_BASE = "./img"
SND_BASE = "./sound"

# 将路径转成 Image 对象；若主名不存在则用已知别名兜底
from js import Image
def _to_img(path):
    try:
        if hasattr(window, "PRELOADED_IMAGES"):
            keys = [
                path,
                path.replace("./", "/"),
                path.lstrip("./"),
                "/" + path.lstrip("./")
            ]
            for k in keys:
                try:
                    pre = window.PRELOADED_IMAGES.get(k) if hasattr(window.PRELOADED_IMAGES, "get") else window.PRELOADED_IMAGES[k]
                    if pre is not None and pre is not False:
                        return pre
                except Exception:
                    continue
    except Exception:
        pass
    try:
        try:
            img = Image.new()
        except Exception:
            img = Image()
        img.src = path
        return img
    except Exception:
        return None

# 首选命名
SPRITES = {
    "bg_01":        f"{IMG_BASE}/bg_01.jpg",
    "bg_02":        f"{IMG_BASE}/bg_02.jpg",
    "player_blue":  f"{IMG_BASE}/blue_plane.png",
    "player_red":   f"{IMG_BASE}/red_plane.png",
    "player_purple":f"{IMG_BASE}/purple_plane.png",
    "enemy_small":  f"{IMG_BASE}/small_enemy.png",
    "enemy_big":    f"{IMG_BASE}/big_enemy.png",
    "boss":         f"{IMG_BASE}/boss_enemy.png",
    "bullet_red":   f"{IMG_BASE}/red_bullet.png",
    "bullet_blue":  f"{IMG_BASE}/blue_bullet.png",
    "enemy_bullet": f"{IMG_BASE}/big_enemy_bullet.png",
    "explosion":    f"{IMG_BASE}/boom.png",
    "power_weapon": f"{IMG_BASE}/bullet_goods1.png",
    "power_shield": f"{IMG_BASE}/plane_shield.png",
    "power_heal":   f"{IMG_BASE}/life_goods.png",
    "power_missile":f"{IMG_BASE}/missile_goods.png",
    "text":         f"{IMG_BASE}/text.png",
}
for k, p in list(SPRITES.items()):
    try:
        SPRITES[k] = _to_img(p)
    except Exception:
        SPRITES[k] = None

def _fallback(key, *alts):
    if SPRITES.get(key) is not None:
        return
    for ap in alts:
        try:
            SPRITES[key] = _to_img(ap)
            return
        except Exception:
            continue

_fallback("enemy_small", f"{IMG_BASE}/small.png")
_fallback("enemy_big",   f"{IMG_BASE}/big.png")
_fallback("boss",        f"{IMG_BASE}/boosplane.png")
_fallback("enemy_bullet",f"{IMG_BASE}/bigplane_bullet.png")
_fallback("explosion",   f"{IMG_BASE}/myplaneexplosion.png")
# 备选的武器道具图（存在就换）
_fallback("power_weapon", f"{IMG_BASE}/bullet_goods2.png", f"{IMG_BASE}/purple_bullet_goods.png", f"{IMG_BASE}/red_bullet_goods.png")
_fallback("power_shield", f"{IMG_BASE}/plane_shield.png")
_fallback("power_heal",   f"{IMG_BASE}/life_goods.png")
_fallback("power_missile",f"{IMG_BASE}/missile_goods.png")

SOUNDS = {
    "shoot":  f"{SND_BASE}/shoot.mp3",
    "boom":   f"{SND_BASE}/explosion.mp3",
    "boom2":  f"{SND_BASE}/explosion2.wav",
    "pickup": f"{SND_BASE}/get_goods.wav",
    "button": f"{SND_BASE}/button.wav",
    "bgm":    f"{SND_BASE}/game.mp3",
}

# Helper: 播放声音
def play_sound(key, vol=0.7):
    try:
        from js import Audio
        if key in SOUNDS and SOUNDS[key]:
            a = Audio.new(SOUNDS[key])
            a.volume = vol
            a.play()
    except Exception:
        pass

class Player:
    def __init__(self):
        self.x = canvas.width/2 - 24
        self.y = canvas.height - 120
        self.w = 48
        self.h = 48
        self.speed = 4
        self.hp = 100
        self.sprite_key = "player_blue"
        self.weapon = "single"  # single | twin | spread
        self.shoot_cd = 0
        self.shield = 0  # frames
    def draw(self):
        img = SPRITES.get(self.sprite_key)
        if img:
            try:
                ctx.drawImage(img, self.x, self.y, self.w, self.h)
            except Exception:
                ctx.fillStyle = "#2b7"
                ctx.fillRect(self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = "#2b7"
            ctx.fillRect(self.x, self.y, self.w, self.h)
        if self.shield > 0:
            ctx.strokeStyle = "rgba(0,200,255,0.8)"
            ctx.lineWidth = 3
            ctx.beginPath()
            ctx.arc(self.x + self.w/2, self.y + self.h/2, self.w * 0.7, 0, Math.PI * 2)
            ctx.stroke()
    def shoot(self):
        if self.shoot_cd > 0: return
        self.shoot_cd = 10
        play_sound("shoot", 0.25)
        if self.weapon == "single":
            bullets.append(Bullet(self.x+self.w/2-3, self.y-10, 0, -8, "player"))
        elif self.weapon == "twin":
            bullets.append(Bullet(self.x+6, self.y-10, 0, -8, "player"))
            bullets.append(Bullet(self.x+self.w-12, self.y-10, 0, -8, "player"))
        elif self.weapon == "spread":
            for dx,dy in [(-2,-8),(0,-9),(2,-8)]:
                bullets.append(Bullet(self.x+self.w/2-3, self.y-10, dx, dy, "player"))
    def hit(self, dmg):
        if self.shield>0:
            self.shield = max(0, self.shield - int(dmg*20))
            return
        self.hp -= dmg

class Enemy:
    def __init__(self, kind="small"):
        self.kind = kind
        self.w = 36 if kind=="small" else 64
        self.h = 36 if kind=="small" else 64
        self.x = randf(0, canvas.width-self.w)
        self.y = -self.h - randf(0, 100)
        spd_min, spd_max = DIFF[selected_diff]["enemy_speed"]
        self.vx = randf(-0.6, 0.6)
        self.vy = randf(spd_min, spd_max)
        self.hp = 15 if kind=="small" else 40
        self.cd = 40  # shoot cooldown
    def draw(self):
        key = "enemy_small" if self.kind=="small" else "enemy_big"
        img = SPRITES.get(key)
        if img:
            ctx.drawImage(img, self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = "#a33" if self.kind=="small" else "#833"
            ctx.fillRect(self.x, self.y, self.w, self.h)
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.x = clamp(self.x, 0, canvas.width-self.w)
        # Shoot
        self.cd -= 1
        if self.cd<=0:
            self.cd = int(90 - 30*randf(0,1))
            if Math.random() < DIFF[selected_diff]["bullet_rate"]:
                # fire at player
                tx = player.x + player.w/2
                ty = player.y + player.h/2
                cx = self.x + self.w/2
                cy = self.y + self.h
                vx = tx - cx
                vy = ty - cy
                mag = (vx*vx+vy*vy) ** 0.5 + 1e-5
                vx, vy = vx/mag*3.0, vy/mag*3.0
                bullets.append(Bullet(cx-3, cy, vx, vy, "enemy"))

class Boss:
    def __init__(self):
        self.w = 160
        self.h = 110
        self.x = canvas.width/2 - self.w/2
        self.y = -self.h
        self.vy = 1.2
        self.hp = DIFF[selected_diff]["boss_hp"]
        self.phase = 0
        self.cd = 120
    def draw(self):
        img = SPRITES.get("boss")
        if img: ctx.drawImage(img, self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = "#5522aa"
            ctx.fillRect(self.x, self.y, self.w, self.h)
        # HP bar
        ctx.fillStyle = "rgba(0,0,0,0.5)"
        ctx.fillRect(20, 20, canvas.width-40, 12)
        ctx.fillStyle = "#e33"
        ratio = max(0, self.hp)/DIFF[selected_diff]["boss_hp"]
        ctx.fillRect(20, 20, (canvas.width-40)*ratio, 12)
    def update(self):
        if self.y < 40:
            self.y += self.vy
        self.cd -= 1
        if self.cd<=0:
            self.cd = 80
            self.phase = (self.phase+1) % 3
            self.fire_pattern(self.phase)
    def fire_pattern(self, p):
        cx = self.x + self.w/2
        cy = self.y + self.h
        if p == 0:
            # fan
            for a in range(-40, 41, 10):
                rad = (a/180.0)*Math.PI
                vx, vy = 3*Math.sin(rad), 3*Math.cos(rad)
                bullets.append(Bullet(cx, cy, vx, vy, "enemy"))
        elif p == 1:
            # aimed bursts
            tx, ty = player.x+player.w/2, player.y+player.h/2
            for k in range(12):
                ang = Math.atan2(ty-cy, tx-cx) + (k-6)*0.08
                vx, vy = 3.2*Math.cos(ang), 3.2*Math.sin(ang)
                bullets.append(Bullet(cx, cy, vx, vy, "enemy"))
        else:
            # spiral
            for k in range(24):
                ang = k*0.26 + Math.random()*0.5
                vx, vy = 2.6*Math.cos(ang), 2.6*Math.sin(ang)+0.8
                bullets.append(Bullet(cx, cy, vx, vy, "enemy"))

class Bullet:
    def __init__(self, x, y, vx, vy, owner):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.w, self.h = 6, 12
        self.owner = owner  # 'player' or 'enemy'
    def draw(self):
        if self.owner == "player":
            img = SPRITES.get("bullet_blue" if player.weapon != "single" else "bullet_red")
            if img:
                try:
                    ctx.drawImage(img, self.x, self.y, self.w, self.h)
                except Exception:
                    ctx.fillStyle = "#0bf" if player.weapon != "single" else "#f33"
                    ctx.fillRect(self.x, self.y, self.w, self.h)
            else:
                ctx.fillStyle = "#0bf" if player.weapon != "single" else "#f33"
                ctx.fillRect(self.x, self.y, self.w, self.h)
        else:
            img = SPRITES.get("enemy_bullet")
            if img:
                try:
                    ctx.drawImage(img, self.x, self.y, self.w, self.h)
                except Exception:
                    ctx.fillStyle = "#f90"
                    ctx.fillRect(self.x, self.y, self.w, self.h)
            else:
                ctx.fillStyle = "#f90"
                ctx.fillRect(self.x, self.y, self.w, self.h)
    def update(self):
        self.x += self.vx
        self.y += self.vy

class PowerUp:
    def __init__(self, kind, x, y):
        self.kind = kind  # weapon | shield | heal
        self.x, self.y = x, y
        self.w, self.h = 28, 28
        self.vy = 2.0
    def draw(self):
        key = "power_"+self.kind
        img = SPRITES.get(key)
        if img: ctx.drawImage(img, self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = {"weapon":"#0bf","shield":"#0cf","heal":"#0b5"}[self.kind]
            ctx.fillRect(self.x, self.y, self.w, self.h)
    def update(self):
        self.y += self.vy

class Explosion:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 24
    def draw(self):
        img = SPRITES.get("explosion")
        if img:
            ctx.drawImage(img, self.x-20, self.y-20, 40, 40)
        else:
            ctx.fillStyle = f"rgba(255,150,0,{self.t/24})"
            ctx.beginPath()
            ctx.arc(self.x, self.y, (24-self.t)+10, 0, Math.PI*2)
            ctx.fill()
    def update(self):
        self.t -= 1

def rects_collide(a, b):
    ax = a.x; ay = a.y; aw = a.w; ah = a.h
    bx = b.x; by = b.y; bw = b.w; bh = b.h
    return (ax < bx+bw and ax+aw > bx and ay < by+bh and ay+ah > by)

def update_hud():
    score_el.innerText = f"分数：{int(score)}"
    lives_el.innerText = f"生命：{player.hp}"
    level_el.innerText = f"难度：{DIFF_NAME_ZH.get(selected_diff, selected_diff)}"

def spawn_enemy():
    kind = "small" if Math.random() < 0.7 else "big"
    enemies.append(Enemy(kind))

def spawn_power(x, y):
    r = Math.random()
    kind = "weapon" if r<0.5 else ("shield" if r<0.8 else "heal")
    powers.append(PowerUp(kind, x, y))

spawn_boss_at = 10000  # 初始触发大Boss的分数阈值
boss = None

def maybe_spawn_boss():
    global boss
    if boss is None and score >= spawn_boss_at:
        boss = Boss()

def reset_game():
    global player, enemies, bullets, powers, effects, boss, score, frame, game_over, shake
    player = Player()
    try:
        player.x = clamp(player.x, 0, canvas.width - player.w)
        player.y = clamp(player.y, 0, canvas.height - player.h)
    except Exception:
        pass
    enemies.clear(); bullets.clear(); powers.clear(); effects.clear()
    boss = None
    score = 0
    frame = 0
    shake = 0
    game_over = False

# Touch controls: drag to move, tap to shoot
touch_active = False
touch_id = None
def setup_controls():
    def keydown(e):
        k = e.key
        if k in keys:
            try:
                e.preventDefault()
            except Exception:
                pass
            keys[k] = True

    def keyup(e):
        k = e.key
        if k in keys:
            try:
                e.preventDefault()
            except Exception:
                pass
            keys[k] = False

    document.addEventListener("keydown", create_proxy(keydown), {"passive": False})
    document.addEventListener("keyup", create_proxy(keyup), {"passive": False})

    def on_blur(e):
        for kk in list(keys.keys()):
            keys[kk] = False
    window.addEventListener("blur", create_proxy(on_blur))

    def on_touchstart(e):
        global touch_active, touch_id
        t = e.changedTouches[0]
        touch_active = True
        touch_id = t.identifier
        rect = canvas.getBoundingClientRect()
        px = t.clientX - rect.left
        py = t.clientY - rect.top
        player.x = clamp(px - player.w/2, 0, canvas.width-player.w)
        player.y = clamp(py - player.h/2, 0, canvas.height-player.h)
        try:
            e.preventDefault()
        except Exception:
            pass

    def on_touchmove(e):
        global touch_active, touch_id
        if not touch_active:
            return
        t = None
        for touch in e.changedTouches:
            if touch.identifier == touch_id:
                t = touch
                break
        if t:
            try:
                e.preventDefault()
            except Exception:
                pass
            rect = canvas.getBoundingClientRect()
            px = t.clientX - rect.left
            py = t.clientY - rect.top
            player.x = clamp(px - player.w/2, 0, canvas.width-player.w)
            player.y = clamp(py - player.h/2, 0, canvas.height-player.h)

    def on_touchend(e):
        global touch_active, touch_id
        touch_active = False
        touch_id = None

    canvas.addEventListener("touchstart", create_proxy(on_touchstart), {"passive": False})
    canvas.addEventListener("touchmove", create_proxy(on_touchmove), {"passive": False})
    canvas.addEventListener("touchend", create_proxy(on_touchend), {"passive": False})
    canvas.addEventListener("touchcancel", create_proxy(on_touchend), {"passive": False})

setup_controls()

player = Player()
enemies = []
bullets = []
powers = []
effects = []
boss = None
score = 0
frame = 0
bg_offset = 0
shake = 0
spawn_boss_at = 500  # score threshold

keys = {"ArrowLeft":False,"ArrowRight":False,"ArrowUp":False,"ArrowDown":False,"Space":False}

def draw_bg():
    global bg_offset
    # If background images are available, draw a vertically scrolling tiled background.
    try:
        img1 = SPRITES.get("bg_01")
        img2 = SPRITES.get("bg_02")
    except Exception:
        img1 = None
        img2 = None
    imgs = [i for i in (img1, img2) if i]
    if imgs and canvas and ctx:
        # Scroll speed (pixels per frame)
        speed = 1.0
        try:
            bg_offset = (bg_offset + speed) % canvas.height
        except Exception:
            bg_offset = 0
        y = -bg_offset
        idx = 0
        # Draw enough tiles to cover the whole canvas
        while y < canvas.height:
            img = imgs[idx % len(imgs)]
            try:
                ctx.drawImage(img, 0, y, canvas.width, canvas.height)
            except Exception:
                # If drawImage fails, fall back to gradient
                break
            y += canvas.height
            idx += 1
        return

    # Fallback: simple gradient (original)
    g = ctx.createLinearGradient(0,0,0,canvas.height)
    g.addColorStop(0, "#f0f4ff")
    g.addColorStop(1, "#c9e6ff")
    ctx.fillStyle = g
    ctx.fillRect(0,0,canvas.width,canvas.height)

def update():
    global frame, score, game_over, shake, boss
    if state == "menu":
        window.requestAnimationFrame(_raf_proxy)
        return

    # Background
    draw_bg()

    # Player move by keys
    dx = (keys["ArrowRight"]-keys["ArrowLeft"])*player.speed
    dy = (keys["ArrowDown"]-keys["ArrowUp"])*player.speed
    player.x = clamp(player.x+dx, 0, canvas.width-player.w)
    player.y = clamp(player.y+dy, 0, canvas.height-player.h)

    # Shooting：自动连射（无需按键）
    player.shoot()
    if player.shoot_cd > 0:
        player.shoot_cd -= 1
    if player.shield > 0:
        player.shield -= 1

    # Enemies
    if Math.random() < DIFF[selected_diff]["enemy_rate"]:
        spawn_enemy()

    for e in enemies[:]:
        e.update()
        e.draw()
        if e.y > canvas.height+40:
            enemies.remove(e)

    # Boss
    maybe_spawn_boss()
    if boss:
        boss.update()
        boss.draw()

    # Bullets
    for b in bullets[:]:
        b.update()
        b.draw()
        if b.y<-40 or b.y>canvas.height+40 or b.x<-40 or b.x>canvas.width+40:
            bullets.remove(b)

    # Powers
    for p in powers[:]:
        p.update()
        p.draw()
        if p.y > canvas.height+40:
            powers.remove(p)

    # —— 我方中心判定半径（可按需要微调，像素）——
    PLAYER_HIT_RADIUS = 12
    def _cx(obj):
        return obj.x + (getattr(obj, 'w', getattr(obj, 'width', 0))) / 2
    def _cy(obj):
        return obj.y + (getattr(obj, 'h', getattr(obj, 'height', 0))) / 2
    def player_center_hit(obj, radius=PLAYER_HIT_RADIUS):
        px, py = _cx(player), _cy(player)
        ox, oy = _cx(obj), _cy(obj)
        dx, dy = ox - px, oy - py
        return dx*dx + dy*dy <= radius*radius
    
    # Collisions
    for b in [bb for bb in bullets if bb.owner=="player"]:
        for e in enemies[:]:
            if rects_collide(b, e):
                effects.append(Explosion(b.x, b.y))
                play_sound("boom", 0.25)
                bullets.remove(b); e.hp -= 20
                if e.hp<=0:
                    score += 10 if e.kind=="small" else 25
                    if Math.random()<0.25: spawn_power(e.x+e.w/2, e.y+e.h/2)
                    enemies.remove(e)
                break
        if boss and rects_collide(b, boss):
            effects.append(Explosion(b.x, b.y))
            play_sound("boom2", 0.25)
            bullets.remove(b); boss.hp -= 12
            score += 2
            if boss.hp<=0:
                score += 300
                effects.append(Explosion(boss.x+boss.w/2, boss.y+boss.h/2))
                boss = None

    # Enemy bullets vs player
    for b in [bb for bb in bullets if bb.owner=="enemy"]:
        if player_center_hit(e):
            effects.append(Explosion(player.x+player.w/2, player.y+player.h/2))
            play_sound("boom", 0.25)
            try: bullets.remove(b)
            except: pass
            player.hit(15)
            shake = 8

    # Enemy body vs player
    for e in enemies[:]:
        if player_center_hit(b):
            effects.append(Explosion(player.x+player.w/2, player.y+player.h/2))
            play_sound("boom", 0.25)
            enemies.remove(e)
            player.hit(25)
            shake = 10

    # Power pickup
    for p in powers[:]:
        if rects_collide(p, player):
            play_sound("pickup", 0.35)
            if p.kind=="weapon":
                if player.weapon=="single":
                    player.weapon="twin"; player.sprite_key="player_red"
                elif player.weapon=="twin":
                    player.weapon="spread"; player.sprite_key="player_purple"
                else:
                    player.weapon="spread"
            elif p.kind=="shield":
                player.shield = 300
            else:
                player.hp = min(100, player.hp+30)
            powers.remove(p)

    # Draw player last
    player.draw()

    # Effects
    for fx in effects[:]:
        fx.update(); fx.draw()
        if fx.t<=0: effects.remove(fx)

    # Shake (装饰)
    if shake>0:
        shake -= 1
        ctx.save()
        ctx.translate(randf(-2,2), randf(-2,2))
        ctx.restore()

    frame += 1
    score += 0.03  # time bonus
    update_hud()

    if player.hp <= 0:
        end_game()
        return

    window.requestAnimationFrame(_raf_proxy)

def end_game():
    global state, game_over
    state = "gameover"; game_over = True
    document.body.classList.remove("playing")

    try:
        if hasattr(window, "__bgm_audio") and window.__bgm_audio:
            try:
                window.__bgm_audio.pause()
            except Exception:
                pass
            try:
                window.__bgm_audio.currentTime = 0
            except Exception:
                pass
    except Exception:
        pass

    # 绘制 GAME OVER 覆盖层
    ctx.fillStyle = "rgba(0,0,0,0.45)"
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = "red"
    ctx.font = "42px Arial"
    ctx.fillText("GAME OVER", canvas.width/2 - 120, canvas.height/2)
    # show menu after short delay
    def show_menu(*args):
        menu.style.display = "flex"
    window.setTimeout(create_proxy(show_menu), 900)

# Hook start button
def on_start(evt):
    global state
    play_sound("button", 0.4)
    menu.style.display = "none"
    # Try to start background music (looped); use a persistent Audio object on window
    try:
        from js import Audio
        try:
            if hasattr(window, '__bgm_audio') and window.__bgm_audio:
                try:
                    window.__bgm_audio.pause()
                except Exception:
                    pass
        except Exception:
            pass
        if "bgm" in SOUNDS and SOUNDS.get("bgm"):
            a = Audio.new(SOUNDS.get("bgm"))
            try:
                a.loop = True
            except Exception:
                pass
            try:
                a.volume = 0.35
            except Exception:
                pass
            try:
                a.play()
            except Exception:
                # Some browsers require play after user gesture; this is called by click, should be fine
                pass
            try:
                window.__bgm_audio = a
            except Exception:
                pass
    except Exception as e:
        console.warn("start bgm failed: " + str(e))

    # 读取当前选中的难度按钮，确保与菜单一致
    try:
        active = menu.querySelector(".btns button.active")
        if active:
            sd = active.getAttribute("data-diff")
            if sd:
                global selected_diff
                selected_diff = sd
    except Exception:
        pass

    document.body.classList.add("playing")
    reset_game()
    state = "playing"
    window.requestAnimationFrame(_raf_proxy)

start_btn.addEventListener("click", create_proxy(on_start))
# —— 同步用户可能在 Pyodide 初始化期间的点击/选择 —— 
try:
    if hasattr(window, "__desiredDifficulty") and window.__desiredDifficulty:
        # 让 Python 端的选中状态与菜单一致
        global selected_diff
        selected_diff = str(window.__desiredDifficulty)
        # 更新菜单按钮的 active 外观
        for i in range(diff_buttons.length):
            b = diff_buttons.item(i)
            if b.getAttribute("data-diff") == selected_diff:
                try:
                    b.classList.add("active")
                except Exception:
                    pass
            else:
                try:
                    b.classList.remove("active")
                except Exception:
                    pass
except Exception:
    pass

try:
    if hasattr(window, "__startClicked") and window.__startClicked:
        on_start(None)  # 立即开始游戏
        window.__startClicked = False
except Exception:
    pass

# Initial render (menu visible)
def first_frame():
    draw_bg()
    ctx.fillStyle = "rgba(0,0,0,0.45)"
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = "white"
    ctx.font = "24px Arial"

_raf_proxy = create_proxy(lambda *_: update())
first_frame()
