from js import document, window, console, Math
from pyodide.ffi import create_proxy
from utils import rects_collide, clamp, randf, load_sprite

# ---- safe remove helper to avoid "list.remove(x): x not in list" ----
def safe_remove(seq, item):
    try:
        seq.remove(item)
    except ValueError:
        pass

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
life_fill_el = document.getElementById("life-fill")
life_text_el = document.getElementById("life-text")
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

# --- Dynamic difficulty scaling (based on current score) ---
# regardless of the initially selected difficulty.
_DIFFICULTY_THRESHOLDS = [2000, 6000, 12000, 20000, 30000, 45000, 60000, 80000, 105000]

def _difficulty_tier(sc):
    t = 0
    for th in _DIFFICULTY_THRESHOLDS:
        if sc >= th:
            t += 1
        else:
            break
    return t

def _scale_param(key, value, tier):
    # gentle but noticeable scaling; capped to keep the game fair
    if key == "enemy_rate":
        return min(value * (1 + 0.12 * tier), 0.09)
    if key == "enemy_speed":
        a, b = value
        mul = 1 + 0.08 * tier
        return (a * mul, b * mul)
    if key == "bullet_rate":
        return min(value * (1 + 0.10 * tier), 0.06)
    if key == "boss_hp":
        # Make later bosses tougher
        return int(value * (1 + 0.18 * tier))
    return value

class _ParamView:
    def __init__(self, base):
        self._base = base
    def __getitem__(self, k):
        try:
            sc = score
        except Exception:
            sc = 0
        tier = _difficulty_tier(int(sc))
        return _scale_param(k, self._base[k], tier)

class _DiffProxy:
    def __init__(self, base):
        self._base = base
    def __getitem__(self, name):
        return _ParamView(self._base[name])

# Replace static DIFF with proxy (keep original as _BASE_DIFF in case you need it)
_BASE_DIFF = DIFF
DIFF = _DiffProxy(_BASE_DIFF)
,
    "normal": {"enemy_rate": 0.022, "enemy_speed": (1.8,2.8), "bullet_rate": 0.008, "boss_hp": 1800},
    "hard":   {"enemy_rate": 0.03,  "enemy_speed": (2.6,3.6), "bullet_rate": 0.012, "boss_hp": 2400},
}
DIFF_NAME_ZH = {"easy": "简单", "normal": "普通", "hard": "困难"}
WEAPON_TIERS = ("single", "twin", "spread")
TIER_TO_SPRITE = {
    "single": "player_blue",
    "twin":   "player_red",
    "spread": "player_purple",
}
def _apply_tier_sprite(plr):
    try:
        plr.sprite_key = TIER_TO_SPRITE.get(plr.weapon, plr.sprite_key)
    except Exception:
        pass

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
    "player_blue":  f"{IMG_BASE}/blue_plane.png",
    "player_red":   f"{IMG_BASE}/red_plane.png",
    "player_purple":f"{IMG_BASE}/purple_plane.png",
    "enemy_small":  f"{IMG_BASE}/small_enemy.png",
    "enemy_big":    f"{IMG_BASE}/big_enemy.png",
    "enemy_medium": f"{IMG_BASE}/middle_enemy.png",
    "boss":         f"{IMG_BASE}/boss_enemy.png",
    "boss_crazy":   f"{IMG_BASE}/bossplane_crazy.png",
    "boss_bomb":    f"{IMG_BASE}/bossplane_bomb.png",
    "bullet_red":   f"{IMG_BASE}/red_bullet.png",
    "bullet_blue":  f"{IMG_BASE}/blue_bullet.png",
    "enemy_bullet": f"{IMG_BASE}/big_enemy_bullet.png",
    "explosion":    f"{IMG_BASE}/boom.png",
    "power_weapon": f"{IMG_BASE}/bullet_goods1.png",
    "power_shield": f"{IMG_BASE}/plane_shield.png",
    "power_heal":   f"{IMG_BASE}/life_goods.png",
    "power_missile":f"{IMG_BASE}/missile_goods.png",
    "text":         f"{IMG_BASE}/text.png",
    "boss_bullet_default": f"{IMG_BASE}/boss_bullet_default.png",
    "boss_bullet_triangle": f"{IMG_BASE}/boss_bullet_triangle.png",
    "boss_bullet_thunderball_red": f"{IMG_BASE}/boss_bullet_thunderball_red.png",
    "boss_bullet_thunderball_green": f"{IMG_BASE}/boss_bullet_thunderball_green.png",
    "boss_bullet_hellfire_red": f"{IMG_BASE}/boss_bullet_hellfire_red.png",
    "boss_bullet_hellfire_yellow": f"{IMG_BASE}/boss_bullet_hellfire_yellow.png",
    "boss_bullet_sun_particle": f"{IMG_BASE}/boss_bullet_sun_particle.png",
    # Aliases used by some resource packs
    "bossbullet_default": f"{IMG_BASE}/bossbullet_default.png",
    # Player bullet variants
    "my_bullet_red": f"{IMG_BASE}/my_bullet_red.png",
    "my_bullet_blue": f"{IMG_BASE}/my_bullet_blue.png",
    "my_bullet_purple": f"{IMG_BASE}/my_bullet_purple.png",
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

bg_offscreen = None
_bg_offscreen_width = 0
_bg_offscreen_height = 0

def build_bg_offscreen():
    """Build a tall offscreen canvas (2x screen height) with a procedurally generated dark starfield."""
    global bg_offscreen, _bg_offscreen_width, _bg_offscreen_height
    try:
        w = int(Math.floor(canvas.width)) or 1
        h = int(Math.floor(canvas.height)) or 1
        off = document.createElement("canvas")
        off.width = w
        off.height = h * 2
        offctx = off.getContext("2d")

        # Background: deep space gradient
        try:
            g = offctx.createLinearGradient(0, 0, 0, off.height)
            g.addColorStop(0, "#03050a")
            g.addColorStop(1, "#000000")
            offctx.fillStyle = g
        except Exception:
            offctx.fillStyle = "#000"
        offctx.fillRect(0, 0, off.width, off.height)

        # Star layers (parallax baked into scroll)
        import math as _py_math
        def _lay(count, minr, maxr, alpha_min, alpha_max):
            for i in range(count):
                x = Math.floor(Math.random() * w)
                y = Math.floor(Math.random() * (h * 2))
                r = randf(minr, maxr)
                a = randf(alpha_min, alpha_max)
                try:
                    offctx.beginPath()
                    offctx.globalAlpha = a
                    offctx.arc(x, y, r, 0, Math.PI * 2)
                    offctx.fillStyle = "#ffffff"
                    offctx.fill()
                except Exception:
                    # Fallback tiny pixel
                    offctx.globalAlpha = a
                    offctx.fillStyle = "#ffffff"
                    offctx.fillRect(x, y, 1, 1)
            offctx.globalAlpha = 1.0

        area = w * h
        # Densities scale with area to keep similar feel across screens
        _lay(max(80, int(area / 4500)), 0.6, 1.2, 0.35, 0.7)   # distant faint stars
        _lay(max(40, int(area / 9000)), 1.0, 1.8, 0.6, 0.9)    # mid stars
        _lay(max(16, int(area / 15000)), 1.6, 2.4, 0.8, 1.0)   # near bright stars

        # Occasional soft nebula swirls
        try:
            for _ in range(max(1, int(area / 220000))):
                cx = randf(0, w); cy = randf(0, h * 2)
                rx = randf(120, 240); ry = randf(60, 140)
                offctx.save()
                offctx.translate(cx, cy)
                offctx.rotate(randf(0, Math.PI))
                grd = offctx.createRadialGradient(0,0,0, 0,0, max(rx, ry))
                grd.addColorStop(0.0, "rgba(30,60,120,0.12)")
                grd.addColorStop(1.0, "rgba(0,0,0,0)")
                offctx.fillStyle = grd
                offctx.beginPath()
                offctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2)
                offctx.fill()
                offctx.restore()
        except Exception:
            pass

        bg_offscreen = off
        _bg_offscreen_width = off.width
        _bg_offscreen_height = off.height
    except Exception:
        try:
            window.setTimeout(create_proxy(build_bg_offscreen), 500)
        except Exception:
            pass

build_bg_offscreen()

SOUNDS = {
    "shoot":  f"{SND_BASE}/shoot.mp3",
    "boom":   f"{SND_BASE}/explosion.mp3",
    "boom2":  f"{SND_BASE}/explosion2.wav",
    "pickup": f"{SND_BASE}/get_goods.wav",
    "button": f"{SND_BASE}/button.wav",
    "bgm":    f"{SND_BASE}/game.mp3",
    "boom3":  f"{SND_BASE}/explosion3.wav",
    "bigboom": f"{SND_BASE}/bigexplosion.wav",
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
        self.homing_combo = False
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
        if self.shoot_cd > 0:
            return
        self.shoot_cd = 10
        play_sound("shoot", 0.25)
        if self.homing_combo:
            bullets.append(Bullet(self.x + self.w/2 - 3, self.y - 10, 0, -8, "player"))
            bullets.append(Bullet(self.x + self.w/2 - 3, self.y - 12, 0, -6, "player", homing=True))
            return
        if self.weapon == "single":
            bullets.append(Bullet(self.x + self.w/2 - 3, self.y - 10, 0, -8, "player"))
        elif self.weapon == "twin":
            bullets.append(Bullet(self.x + 6, self.y - 10, 0, -8, "player"))
            bullets.append(Bullet(self.x + self.w - 12, self.y - 10, 0, -8, "player"))
        elif self.weapon == "spread":
            for dx, dy in [(-2, -8), (0, -9), (2, -8)]:
                bullets.append(Bullet(self.x + self.w/2 - 3, self.y - 10, dx, dy, "player"))
    def hit(self, dmg):
        if self.shield > 0:
            self.shield = max(0, self.shield - int(dmg * 20))
            return False
        self.hp -= dmg
        if self.homing_combo:
            self.homing_combo = False
            self.weapon = "spread"
            _apply_tier_sprite(self)
            return True
        try:
            idx = WEAPON_TIERS.index(self.weapon)
        except Exception:
            idx = 0
        if idx > 0:
            self.weapon = WEAPON_TIERS[idx - 1]
            _apply_tier_sprite(self)
        return True

class Enemy:
    def __init__(self, kind="small"):
        self.kind = kind
        self.w = 36 if kind=="small" else (64 if kind=="big" else 48)
        self.h = 36 if kind=="small" else (64 if kind=="big" else 48)
        self.x = randf(0, canvas.width-self.w)
        self.y = -self.h - randf(0, 100)
        spd_min, spd_max = DIFF[selected_diff]["enemy_speed"]
        self.vx = randf(-0.6, 0.6)
        self.vy = randf(spd_min, spd_max)
        self.hp = 15 if kind=="small" else (40 if kind=="big" else 28)
        self.cd = 40  # shoot cooldown
    def draw(self):
        key = "enemy_small" if self.kind=="small" else ("enemy_big" if self.kind=="big" else "enemy_medium")
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
        self.vx = 2.0
        self.hp = DIFF[selected_diff]["boss_hp"]
        self.phase = 0
        self.cd = 120
    def draw(self):
        key = "boss_crazy" if getattr(self, "phase", 0) == 2 and SPRITES.get("boss_crazy") else "boss"
        img = SPRITES.get(key)
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
        # Enter from top, then patrol horizontally at y=40
        if self.y < 40:
            self.y += self.vy
        else:
            # Horizontal patrol & edge bounce
            self.x += self.vx
            if self.x <= 0 or self.x + self.w >= canvas.width:
                self.vx = -self.vx
                self.x = clamp(self.x, 0, canvas.width - self.w)
        # Shoot pattern cycling
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
                bullets.append(Bullet(cx, cy, vx, vy, "enemy", sprite_key="boss_bullet_default"))
        elif p == 1:
            # aimed bursts
            tx, ty = player.x+player.w/2, player.y+player.h/2
            for k in range(12):
                ang = Math.atan2(ty-cy, tx-cx) + (k-6)*0.08
                vx, vy = 3.2*Math.cos(ang), 3.2*Math.sin(ang)
                bullets.append(Bullet(cx, cy, vx, vy, "enemy", sprite_key=("boss_bullet_thunderball_red" if (k % 2 == 0) else "boss_bullet_thunderball_green")))
        else:
            # spiral
            for k in range(24):
                ang = k*0.26 + Math.random()*0.5
                vx, vy = 2.6*Math.cos(ang), 2.6*Math.sin(ang)+0.8
                bullets.append(Bullet(cx, cy, vx, vy, "enemy", sprite_key="boss_bullet_sun_particle"))

class Bullet:
    def __init__(self, x, y, vx, vy, owner, sprite_key=None, w=None, h=None, homing=False, speed=None):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.w, self.h = (w or 6), (h or 12)
        self.owner = owner  # 'player' or 'enemy'
        self.sprite_key = sprite_key
        self.homing = homing
        try:
            vlen = Math.sqrt(vx*vx + vy*vy)
        except Exception:
            vlen = 0
        self.speed = speed or (vlen or 7.0)
    def draw(self):
        if self.owner == "player":
            if getattr(self, "homing", False):
                img = SPRITES.get("my_bullet_blue") or SPRITES.get("blue_bullet") or SPRITES.get("bullet_blue")
            elif player.weapon == "single":
                img = SPRITES.get("my_bullet_red") or SPRITES.get("bullet_red")
            else:
                # Twin/Spread
                if getattr(player, "sprite_key", "") == "player_purple":
                    img = SPRITES.get("my_bullet_purple") or SPRITES.get("bullet_blue")
                else:
                    img = SPRITES.get("my_bullet_blue") or SPRITES.get("bullet_blue")
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
            img = SPRITES.get(self.sprite_key) or SPRITES.get("enemy_bullet")
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
        if getattr(self, "homing", False) and self.owner == "player":
            target = None
            try:
                if boss:
                    target = boss
            except Exception:
                target = None
            if not target:
                nearest = None
                nearest_d2 = 1e12
                for e in enemies:
                    dx = (e.x + e.w/2) - (self.x + self.w/2)
                    dy = (e.y + e.h/2) - (self.y + self.h/2)
                    d2 = dx*dx + dy*dy
                    if d2 < nearest_d2:
                        nearest_d2 = d2; nearest = e
                target = nearest
            if target:
                dx = (target.x + target.w/2) - (self.x + self.w/2)
                dy = (target.y + target.h/2) - (self.y + self.h/2)
                try:
                    dist = Math.sqrt(dx*dx + dy*dy) or 1
                except Exception:
                    dist = (abs(dx)+abs(dy)) or 1
                spd = getattr(self, "speed", None)
                if not spd or spd<=0:
                    spd = 7.0
                desired_vx = dx / dist * spd
                desired_vy = dy / dist * spd
                self.vx = self.vx*0.6 + desired_vx*0.4
                self.vy = self.vy*0.6 + desired_vy*0.4
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
    level_el.innerText = f"难度：{DIFF_NAME_ZH.get(selected_diff, selected_diff)}｜动态+{_difficulty_tier(int(score))}"

def spawn_enemy():
    r = Math.random()
    kind = "small" if r < 0.55 else ("medium" if r < 0.85 else "big")
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
    _apply_tier_sprite(player)
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

    def on_touchstart(e):
        global touch_active, touch_id
        try:
            t = e.changedTouches[0]
        except Exception:
            return
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
                rect = canvas.getBoundingClientRect()
                px = t.clientX - rect.left
                py = t.clientY - rect.top
                player.x = clamp(px - player.w/2, 0, canvas.width-player.w)
                player.y = clamp(py - player.h/2, 0, canvas.height-player.h)
                try:
                    e.preventDefault()
                except Exception:
                    pass
            except Exception:
                pass

    def on_touchend(e):
        global touch_active, touch_id
        touch_active = False
        touch_id = None

    def on_pointerdown(e):
        global touch_active, touch_id
        touch_active = True
        try:
            touch_id = e.pointerId
        except Exception:
            touch_id = None
        rect = canvas.getBoundingClientRect()
        px = e.clientX - rect.left
        py = e.clientY - rect.top
        player.x = clamp(px - player.w/2, 0, canvas.width-player.w)
        player.y = clamp(py - player.h/2, 0, canvas.height-player.h)
        try:
            e.preventDefault()
        except Exception:
            pass

    def on_pointermove(e):
        if not touch_active:
            return
        try:
            rect = canvas.getBoundingClientRect()
            px = e.clientX - rect.left
            py = e.clientY - rect.top
            player.x = clamp(px - player.w/2, 0, canvas.width-player.w)
            player.y = clamp(py - player.h/2, 0, canvas.height-player.h)
            try:
                e.preventDefault()
            except Exception:
                pass
        except Exception:
            pass

    def on_pointerup(e):
        global touch_active, touch_id
        touch_active = False
        touch_id = None

    canvas.addEventListener("keydown", create_proxy(keydown))
    try:
        window.addEventListener("keydown", create_proxy(keydown))
    except Exception:
        pass
    canvas.addEventListener("keyup", create_proxy(keyup))
    try:
        window.addEventListener("keyup", create_proxy(keyup))
    except Exception:
        pass
    # Touch
    canvas.addEventListener("touchstart", create_proxy(on_touchstart), {"passive": False})
    canvas.addEventListener("touchmove", create_proxy(on_touchmove), {"passive": False})
    canvas.addEventListener("touchend", create_proxy(on_touchend), {"passive": False})
    canvas.addEventListener("touchcancel", create_proxy(on_touchend), {"passive": False})
    # Pointer fallback
    try:
        canvas.addEventListener("pointerdown", create_proxy(on_pointerdown))
        canvas.addEventListener("pointermove", create_proxy(on_pointermove))
        canvas.addEventListener("pointerup", create_proxy(on_pointerup))
        canvas.addEventListener("pointercancel", create_proxy(on_pointerup))
    except Exception:
        pass

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
    global bg_offset, bg_offscreen, _bg_offscreen_width, _bg_offscreen_height
    try:
        # Use the pre-rendered starfield if ready
        if bg_offscreen and _bg_offscreen_width == canvas.width and _bg_offscreen_height == canvas.height * 2:
            speed = 1.0
            try:
                bg_offset = (bg_offset + speed) % canvas.height
            except Exception:
                bg_offset = 0
            try:
                ctx.drawImage(bg_offscreen, 0, bg_offset - canvas.height, canvas.width, _bg_offscreen_height)
                return
            except Exception:
                pass
        # Rebuild if size changed or not ready yet
        try:
            build_bg_offscreen()
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: simple dark gradient fill
    try:
        g = ctx.createLinearGradient(0,0,0,canvas.height)
        g.addColorStop(0, "#05070d")
        g.addColorStop(1, "#000000")
        ctx.fillStyle = g
        ctx.fillRect(0,0,canvas.width,canvas.height)
    except Exception:
        try:
            ctx.fillStyle = "#000"
            ctx.fillRect(0,0,canvas.width,canvas.height)
        except Exception:
            pass

def update():
    global frame, score, game_over, shake, boss, spawn_boss_at
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

    maybe_spawn_boss()
    if boss:
        boss.update()
        boss.draw()

    if Math.random() < DIFF[selected_diff]["enemy_rate"]:
        if boss is None:
            spawn_enemy()
        else:
            if selected_diff == "easy":
                pass
            elif selected_diff == "normal":
                enemies.append(Enemy("small"))
            else:
                spawn_enemy()

    for e in enemies[:]:
        e.update()
        e.draw()
        if e.y > canvas.height + 40:
            enemies.remove(e)

    # Bullets
    for b in bullets[:]:
        b.update()
        b.draw()
        if b.y<-40 or b.y>canvas.height+40 or b.x<-40 or b.x>canvas.width+40:
            safe_remove(bullets, b)

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
                safe_remove(bullets, b); e.hp -= 20
                if e.hp<=0:
                    score += 10 if e.kind=="small" else 25
                    if Math.random()<0.25: spawn_power(e.x+e.w/2, e.y+e.h/2)
                    safe_remove(enemies, e)
                break
        if boss and rects_collide(b, boss):
            effects.append(Explosion(b.x, b.y))
            play_sound("boom2", 0.25)
            try:
                safe_remove(bullets, b)
            except Exception:
                pass
            try:
                boss.hp -= 12
            except Exception:
                boss.hp = 0
            score += 2

            if boss.hp <= 0:
                score += 300
                effects.append(Explosion(boss.x+boss.w/2, boss.y+boss.h/2))
                play_sound("bigboom", 0.6)  # optional big explosion
                boss = None
                try:
                    spawn_boss_at = score + 1000
                except Exception:
                    pass

    # Enemy bullets vs player
    for b in [bb for bb in bullets if bb.owner=="enemy"]:
        if player_center_hit(b):
            damaged = player.hit(15)
            safe_remove(bullets, b)
            if damaged:
                effects.append(Explosion(player.x+player.w/2, player.y+player.h/2))
                play_sound("boom", 0.25)
                shake = 8
            else:
                pass

    # Enemy body vs player
    for e in enemies[:]:
        if player_center_hit(e):
            damaged = player.hit(25)
            safe_remove(enemies, e)
            if damaged:
                effects.append(Explosion(player.x+player.w/2, player.y+player.h/2))
                play_sound("boom", 0.25)
                shake = 10
            else:
                pass

    # Power pickup
    for p in powers[:]:
        if rects_collide(p, player):
            play_sound("pickup", 0.35)
            if p.kind == "weapon":
                if player.weapon == "single":
                    player.weapon = "twin"
                    _apply_tier_sprite(player)
                elif player.weapon == "twin":
                    player.weapon = "spread"
                    _apply_tier_sprite(player)
                else:
                    if player.hp >= 100:
                        player.homing_combo = True
                try:
                    delattr(player, "fallback_single")
                except Exception:
                    pass
            elif p.kind=="shield":
                player.shield = 300
            else:
                player.hp = min(100, player.hp+30)
            safe_remove(powers, p)

    # Draw player last
    player.draw()

    # Effects
    for fx in effects[:]:
        fx.update(); fx.draw()
        if fx.t<=0:
            safe_remove(effects, fx)

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
    try:
        document.getElementById('game-canvas').focus()
    except Exception:
        pass
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
        on_start(None)
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
