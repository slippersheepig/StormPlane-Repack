from js import document, window, Math, Image, Audio
from pyodide.ffi import create_proxy
from utils import rects_collide, clamp, randf


# ====== 游戏核心常量与配置 ======
IMG_BASE = "./img"
SND_BASE = "./sound"
STORAGE_BEST_KEY = "stormplane_best_score"
STORAGE_MUTE_KEY = "stormplane_muted"

STEP_MS = 1000.0 / 60.0
INITIAL_BOSS_SCORE = 500
BOSS_SCORE_INTERVAL = 1000
PLAYER_HIT_RADIUS = 11
PLAYER_INVULN_FRAMES = 24
CLEAR_WAVE_DURATION = 60 * 5
CLEAR_WAVE_PULSE_GAP = 12
SHIELD_DURATION = 60 * 5

# 实体数量上限（保障低端设备与 Pyodide 运行流畅）
MAX_ENEMIES = 42
MAX_BULLETS = 220
MAX_EFFECTS = 50
MAX_PARTICLES = 90
MAX_FLOATING_TEXTS = 18
MAX_POWERS = 18

BASE_DIFF = {
    "easy": {
        "enemy_rate": 0.015,
        "enemy_speed": (1.0, 2.0),
        "bullet_rate": 0.004,
        "boss_hp": 1200,
    },
    "normal": {
        "enemy_rate": 0.022,
        "enemy_speed": (1.8, 2.8),
        "bullet_rate": 0.008,
        "boss_hp": 1800,
    },
    "hard": {
        "enemy_rate": 0.030,
        "enemy_speed": (2.6, 3.6),
        "bullet_rate": 0.012,
        "boss_hp": 2400,
    },
}

DIFF_THRESHOLDS = (2000, 6000, 12000, 20000, 30000, 45000, 60000, 80000, 105000)
DIFF_NAME_ZH = {"easy": "简单", "normal": "普通", "hard": "困难"}
WEAPON_TIERS = ("single", "twin", "spread")

TIER_META = {
    "single": {
        "sprite": "player_blue",
        "label": "蓝刃",
        "outer": "rgba(64, 205, 255, 0.34)",
        "inner": "#3fd8ff",
        "core": "#e6fcff",
        "flame_outer": "rgba(0, 210, 255, 0.55)",
        "flame_inner": "#d8fbff",
        "explosion_col": 0,
    },
    "twin": {
        "sprite": "player_red",
        "label": "赤炎",
        "outer": "rgba(255, 90, 72, 0.36)",
        "inner": "#ff5b49",
        "core": "#ffe5dc",
        "flame_outer": "rgba(255, 110, 48, 0.62)",
        "flame_inner": "#fff0c2",
        "explosion_col": 4,
    },
    "spread": {
        "sprite": "player_purple",
        "label": "紫电",
        "outer": "rgba(198, 102, 255, 0.38)",
        "inner": "#d46bff",
        "core": "#fcebff",
        "flame_outer": "rgba(192, 92, 255, 0.62)",
        "flame_inner": "#f6dcff",
        "explosion_col": 2,
    },
}

ENEMY_SPECS = {
    "small": {"w": 38, "h": 40, "hp": 15, "score": 10, "sprite": "enemy_small"},
    "medium": {"w": 46, "h": 62, "hp": 28, "score": 25, "sprite": "enemy_medium"},
    "big": {"w": 68, "h": 78, "hp": 44, "score": 40, "sprite": "enemy_big"},
}

SOUND_FILES = {
    "shoot": f"{SND_BASE}/shoot.mp3",
    "boom": f"{SND_BASE}/explosion.mp3",
    "boom2": f"{SND_BASE}/explosion2.wav",
    "boom3": f"{SND_BASE}/explosion3.wav",
    "bigboom": f"{SND_BASE}/bigexplosion.wav",
    "pickup": f"{SND_BASE}/get_goods.wav",
    "button": f"{SND_BASE}/button.wav",
    "bgm": f"{SND_BASE}/game.mp3",
}

SOUND_RATE_LIMIT_MS = {
    "shoot": 80,
    "boom": 70,
    "boom2": 90,
    "boom3": 160,
    "pickup": 40,
    "button": 0,
    "bigboom": 0,
}

# 持久化保存 Pyodide 事件代理，避免被 GC 回收或重复泄漏
_proxies = []


def _keep_proxy(fn):
    proxy = create_proxy(fn)
    _proxies.append(proxy)
    return proxy


def _js_dict_get(js_obj, key):
    """安全读取 JS 普通对象属性，兼容 Pyodide JsProxy。"""
    if js_obj is None:
        return None
    try:
        val = js_obj[key]
        return val if val is not None else None
    except Exception:
        return None


def _is_img_ready(img):
    return (
        img is not None
        and getattr(img, "complete", False)
        and getattr(img, "naturalWidth", 0) > 0
    )


def safe_remove(seq, item):
    try:
        seq.remove(item)
    except ValueError:
        pass


# ====== 本地存储与难度动态缩放 ======
def _load_best_score():
    try:
        return max(0, int(window.localStorage.getItem(STORAGE_BEST_KEY) or 0))
    except Exception:
        return 0


def _save_best_score(val):
    try:
        window.localStorage.setItem(STORAGE_BEST_KEY, str(int(val)))
    except Exception:
        pass


def _load_muted():
    try:
        return window.localStorage.getItem(STORAGE_MUTE_KEY) == "1"
    except Exception:
        return False


def _save_muted(flag):
    try:
        window.localStorage.setItem(STORAGE_MUTE_KEY, "1" if flag else "0")
    except Exception:
        pass


def get_difficulty_tier(current_score):
    tier = 0
    for threshold in DIFF_THRESHOLDS:
        if current_score >= threshold:
            tier += 1
        else:
            break
    return tier


def get_diff_param(key):
    """根据当前所选难度与分数动态计算参数。"""
    base = BASE_DIFF.get(selected_diff, BASE_DIFF["normal"])
    value = base[key]
    tier = get_difficulty_tier(int(score))

    if key == "enemy_rate":
        return min(value * (1.0 + 0.12 * tier), 0.09)
    if key == "enemy_speed":
        mul = 1.0 + 0.08 * tier
        return (value[0] * mul, value[1] * mul)
    if key == "bullet_rate":
        return min(value * (1.0 + 0.10 * tier), 0.06)
    if key == "boss_hp":
        return int(value * (1.0 + 0.18 * tier))
    return value


# ====== 画布与 DOM 引用 ======
def ensure_canvas_and_ctx():
    c = document.getElementById("game-canvas")
    if c is None:
        container = document.getElementById("game-container") or document.body
        c = document.createElement("canvas")
        c.id = "game-canvas"
        c.style.display = "block"
        container.appendChild(c)
    return c, c.getContext("2d")


canvas, ctx = ensure_canvas_and_ctx()

hud_el = document.getElementById("hud")
hud_controls_el = document.getElementById("hud-controls")
pause_overlay_el = document.getElementById("pause-overlay")

score_el = document.getElementById("score")
lives_el = document.getElementById("lives")
hp_bar_el = document.getElementById("hp-bar")
hp_wrap_el = document.getElementById("hp-wrap")
weapon_badge_el = document.getElementById("weapon-badge")
level_el = document.getElementById("level")

menu_el = document.getElementById("menu")
start_btn = document.getElementById("start-btn")
pause_btn = document.getElementById("pause-btn")
mute_btn = document.getElementById("mute-btn")
resume_btn = document.getElementById("resume-btn")
menu_return_btn = document.getElementById("menu-btn")
menu_record_el = document.getElementById("menu-record")
best_score_val_el = document.getElementById("best-score-val")
last_score_sep_el = document.getElementById("last-score-sep")
last_score_wrap_el = document.getElementById("last-score-wrap")
last_score_val_el = document.getElementById("last-score-val")


# ====== 资源加载（复用页面预加载缓存） ======
def _load_image(path):
    preloaded = getattr(window, "PRELOADED_IMAGES", None)
    cached = _js_dict_get(preloaded, path)
    if cached is not None:
        return cached
    img = Image.new()
    img.src = path
    return img


SPRITE_PATHS = {
    "player_blue": f"{IMG_BASE}/blue_plane.png",
    "player_red": f"{IMG_BASE}/red_plane.png",
    "player_purple": f"{IMG_BASE}/purple_plane.png",
    "enemy_small": f"{IMG_BASE}/small_enemy.png",
    "enemy_medium": f"{IMG_BASE}/middle_enemy.png",
    "enemy_big": f"{IMG_BASE}/big_enemy.png",
    "boss": f"{IMG_BASE}/boss_enemy.png",
    "boss_crazy": f"{IMG_BASE}/bossplane_crazy.png",
    "boss_bomb": f"{IMG_BASE}/bossplane_bomb.png",
    "enemy_bullet": f"{IMG_BASE}/big_enemy_bullet.png",
    "explosion": f"{IMG_BASE}/boom.png",
    "player_explosion": f"{IMG_BASE}/myplaneexplosion.png",
    "power_weapon_purple": f"{IMG_BASE}/bullet_goods1.png",
    "power_weapon_red": f"{IMG_BASE}/bullet_goods2.png",
    "plane_shield": f"{IMG_BASE}/plane_shield.png",
    "power_heal": f"{IMG_BASE}/life_goods.png",
    "boss_bullet_default": f"{IMG_BASE}/boss_bullet_default.png",
    "boss_bullet_triangle": f"{IMG_BASE}/boss_bullet_triangle.png",
    "boss_bullet_thunderball_red": f"{IMG_BASE}/boss_bullet_thunderball_red.png",
    "boss_bullet_thunderball_green": f"{IMG_BASE}/boss_bullet_thunderball_green.png",
    "boss_bullet_hellfire_red": f"{IMG_BASE}/boss_bullet_hellfire_red.png",
    "boss_bullet_hellfire_yellow": f"{IMG_BASE}/boss_bullet_hellfire_yellow.png",
    "boss_bullet_sun_particle": f"{IMG_BASE}/boss_bullet_sun_particle.png",
}

SPRITES = {key: _load_image(path) for key, path in SPRITE_PATHS.items()}


# ====== 音频系统（带对象池、限流与静音控制） ======
muted = _load_muted()
_last_sound_at = {}
_sound_pools = {}
_bgm_audio = None


def _get_pooled_audio(key):
    path = SOUND_FILES.get(key)
    if not path:
        return None
    pool = _sound_pools.setdefault(key, [])
    for inst in pool:
        if getattr(inst, "paused", True) or getattr(inst, "ended", False):
            return inst
    if len(pool) < 4:
        preloaded = getattr(window, "PRELOADED_AUDIO", None)
        base = _js_dict_get(preloaded, path)
        if base is not None:
            try:
                inst = base.cloneNode(True)
            except Exception:
                inst = Audio.new(path)
        else:
            inst = Audio.new(path)
        pool.append(inst)
        return inst
    return pool[0]


def play_sound(key, vol=0.7):
    if muted:
        return
    now = window.performance.now()
    limit = SOUND_RATE_LIMIT_MS.get(key, 0)
    if limit and now - _last_sound_at.get(key, -100000) < limit:
        return
    _last_sound_at[key] = now

    try:
        audio = _get_pooled_audio(key)
        if audio is None:
            return
        audio.currentTime = 0
        audio.volume = vol
        p = audio.play()
        if p is not None and hasattr(p, "catch"):
            p.catch(_noop_proxy)
    except Exception:
        pass


def _start_bgm():
    global _bgm_audio
    if _bgm_audio is None:
        preloaded = getattr(window, "PRELOADED_AUDIO", None)
        base = _js_dict_get(preloaded, SOUND_FILES["bgm"])
        _bgm_audio = base if base is not None else Audio.new(SOUND_FILES["bgm"])
        _bgm_audio.loop = True
        _bgm_audio.volume = 0.34
    try:
        _bgm_audio.currentTime = 0
        if not muted:
            p = _bgm_audio.play()
            if p is not None and hasattr(p, "catch"):
                p.catch(_noop_proxy)
    except Exception:
        pass


def _pause_bgm(reset_pos=False):
    if _bgm_audio is None:
        return
    try:
        _bgm_audio.pause()
        if reset_pos:
            _bgm_audio.currentTime = 0
    except Exception:
        pass


def _sync_mute_button():
    if mute_btn is None:
        return
    glyph = mute_btn.querySelector(".icon-glyph")
    if glyph is not None:
        glyph.textContent = "🔇" if muted else "🔊"
    if muted:
        mute_btn.classList.add("muted")
    else:
        mute_btn.classList.remove("muted")


def toggle_mute(*_args):
    global muted
    muted = not muted
    _save_muted(muted)
    _sync_mute_button()
    if muted:
        _pause_bgm(reset_pos=False)
    elif state == "playing" and not paused:
        if _bgm_audio is not None:
            try:
                p = _bgm_audio.play()
                if p is not None and hasattr(p, "catch"):
                    p.catch(_noop_proxy)
            except Exception:
                pass
        else:
            _start_bgm()


_noop_proxy = _keep_proxy(lambda *_args: None)


# ====== 深空背景与视差星尘 ======
bg_offscreen = None
_bg_w = 0
_bg_h = 0
bg_offset = 0.0
star_streaks = []


def _init_star_streaks():
    star_streaks.clear()
    w = max(1, canvas.width)
    h = max(1, canvas.height)
    count = clamp(int(w / 64), 14, 28)
    for _ in range(count):
        star_streaks.append([
            randf(0, w),
            randf(0, h),
            randf(2.6, 5.2),
            randf(10.0, 24.0),
            randf(0.12, 0.30),
        ])


def build_bg_offscreen():
    """预渲染无缝循环的深空星云与多色星场离屏画布（2 倍屏幕高度）。"""
    global bg_offscreen, _bg_w, _bg_h
    w = max(1, int(Math.floor(canvas.width)))
    h = max(1, int(Math.floor(canvas.height)))
    off = document.createElement("canvas")
    off.width = w
    off.height = h * 2
    octx = off.getContext("2d")

    octx.fillStyle = "#030712"
    octx.fillRect(0, 0, off.width, off.height)

    # 无缝星云光雾：在 y 与 y ± off.height 同步绘制以消除拼接接缝
    nebulae = (
        (w * 0.22, off.height * 0.24, max(w, h) * 0.42, "rgba(18, 78, 168, 0.14)"),
        (w * 0.78, off.height * 0.56, max(w, h) * 0.46, "rgba(92, 38, 168, 0.13)"),
        (w * 0.48, off.height * 0.86, max(w, h) * 0.38, "rgba(0, 148, 196, 0.10)"),
    )
    for nx, ny, nr, color in nebulae:
        for shift in (-off.height, 0, off.height):
            cy = ny + shift
            if cy + nr < 0 or cy - nr > off.height:
                continue
            grad = octx.createRadialGradient(nx, cy, 0, nx, cy, nr)
            grad.addColorStop(0.0, color)
            grad.addColorStop(1.0, "rgba(3, 7, 18, 0)")
            octx.fillStyle = grad
            octx.fillRect(0, max(0, cy - nr), off.width, min(off.height, nr * 2))

    star_colors = ("#ffffff", "#cfefff", "#b8dcff", "#ffe9c7", "#dec8ff")

    def draw_star_layer(count, r_min, r_max, a_min, a_max, with_flare=False):
        for i in range(count):
            sx = randf(0, w)
            sy = randf(0, off.height)
            r = randf(r_min, r_max)
            alpha = randf(a_min, a_max)
            color = star_colors[i % len(star_colors)]
            octx.globalAlpha = alpha
            octx.fillStyle = color
            octx.beginPath()
            octx.arc(sx, sy, r, 0, Math.PI * 2)
            octx.fill()

            if with_flare and i % 3 == 0:
                octx.globalAlpha = alpha * 0.45
                octx.fillRect(sx - r * 2.8, sy - 0.5, r * 5.6, 1.0)
                octx.fillRect(sx - 0.5, sy - r * 2.8, 1.0, r * 5.6)
        octx.globalAlpha = 1.0

    area = w * h
    draw_star_layer(max(45, int(area / 9500)), 0.6, 1.2, 0.35, 0.72)
    draw_star_layer(max(22, int(area / 20000)), 1.0, 1.7, 0.55, 0.88)
    draw_star_layer(max(10, int(area / 36000)), 1.6, 2.3, 0.78, 1.0, with_flare=True)

    bg_offscreen = off
    _bg_w = off.width
    _bg_h = off.height
    _init_star_streaks()


def step_background(speed_mul=1.0):
    global bg_offset
    if _bg_h > 0:
        bg_offset = (bg_offset + 1.15 * speed_mul) % _bg_h
    h = max(1, canvas.height)
    w = max(1, canvas.width)
    for st in star_streaks:
        st[1] += st[2] * speed_mul
        if st[1] - st[3] > h:
            st[0] = randf(0, w)
            st[1] = -st[3]


def draw_background():
    if bg_offscreen is None or _bg_w != canvas.width or _bg_h != canvas.height * 2:
        build_bg_offscreen()

    if bg_offscreen is not None:
        y = bg_offset - _bg_h
        ctx.drawImage(bg_offscreen, 0, y, canvas.width, _bg_h)
        ctx.drawImage(bg_offscreen, 0, y + _bg_h, canvas.width, _bg_h)
    else:
        ctx.fillStyle = "#030712"
        ctx.fillRect(0, 0, canvas.width, canvas.height)

    # 轻量前景流光星尘，提供双层视差速度感
    ctx.fillStyle = "#bfefff"
    for sx, sy, _spd, length, alpha in star_streaks:
        ctx.globalAlpha = alpha
        ctx.fillRect(sx, sy, 1.2, length)
    ctx.globalAlpha = 1.0


def fit_canvas():
    container = document.getElementById("game-container")
    if container is not None:
        rect = container.getBoundingClientRect()
        w, h = rect.width, rect.height
    else:
        w = window.innerWidth or document.documentElement.clientWidth or 320
        h = window.innerHeight or document.documentElement.clientHeight or 480

    w = max(1, int(Math.floor(w)))
    h = max(1, int(Math.floor(h)))
    canvas.style.width = f"{w}px"
    canvas.style.height = f"{h}px"
    canvas.width = w
    canvas.height = h
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.imageSmoothingEnabled = True
    try:
        ctx.imageSmoothingQuality = "medium"
    except Exception:
        pass

    if "player" in globals() and player is not None:
        player.x = clamp(player.x, 0, canvas.width - player.w)
        player.y = clamp(player.y, 0, canvas.height - player.h)
    if "boss" in globals() and boss is not None:
        boss.x = clamp(boss.x, 0, canvas.width - boss.w)

    build_bg_offscreen()


# ====== 视觉特效实体（粒子、光环、精灵帧动画、飘字） ======
class Particle:
    def __init__(self, x, y, vx, vy, color, size=2.8, life=20):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self):
        ratio = max(0.0, self.life / self.max_life)
        r = max(0.8, self.size * ratio)
        ctx.globalAlpha = ratio
        ctx.fillStyle = self.color
        ctx.beginPath()
        ctx.arc(self.x, self.y, r, 0, Math.PI * 2)
        ctx.fill()
        ctx.globalAlpha = 1.0


class RingWave:
    def __init__(self, x, y, max_r, color, line_width=3.0, life=22):
        self.x = x
        self.y = y
        self.max_r = max_r
        self.color = color
        self.line_width = line_width
        self.t = life
        self.max_t = life

    def update(self):
        self.t -= 1

    def draw(self):
        progress = 1.0 - max(0.0, self.t / self.max_t)
        r = 10.0 + (self.max_r - 10.0) * (1.0 - (1.0 - progress) ** 2)
        alpha = max(0.0, (1.0 - progress) * 0.85)
        ctx.save()
        ctx.globalAlpha = alpha
        ctx.strokeStyle = self.color
        ctx.lineWidth = max(1.0, self.line_width * (1.0 - progress * 0.5))
        ctx.beginPath()
        ctx.arc(self.x, self.y, r, 0, Math.PI * 2)
        ctx.stroke()
        ctx.restore()


class Explosion:
    def __init__(self, x, y, size=44, life=22):
        self.x = x
        self.y = y
        self.size = size
        self.t = life
        self.max_t = life

    def update(self):
        self.t -= 1

    def draw(self):
        progress = 1.0 - max(0.0, self.t / self.max_t)
        scale = 0.65 + progress * 0.55
        draw_size = self.size * scale
        half = draw_size / 2
        alpha = max(0.0, 1.0 - progress ** 1.4)
        img = SPRITES.get("explosion")
        if _is_img_ready(img):
            ctx.globalAlpha = alpha
            ctx.drawImage(img, self.x - half, self.y - half, draw_size, draw_size)
            ctx.globalAlpha = 1.0
        else:
            ctx.fillStyle = f"rgba(255, 160, 40, {alpha})"
            ctx.beginPath()
            ctx.arc(self.x, self.y, half, 0, Math.PI * 2)
            ctx.fill()


class SpriteAnim:
    """裁切精灵图逐帧播放动画（支持 Boss 5 帧爆炸与玩家按涂装 2 帧解体）。"""

    def __init__(self, x, y, w, h, sprite_key, frames, frame_ticks=6):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.sprite_key = sprite_key
        self.frames = frames  # 帧切片列表 [(sx, sy, sw, sh), ...]
        self.frame_ticks = frame_ticks
        self.elapsed = 0
        self.t = len(frames) * frame_ticks

    def update(self):
        self.elapsed += 1
        self.t -= 1

    def draw(self):
        img = SPRITES.get(self.sprite_key)
        if not _is_img_ready(img):
            return
        idx = min(len(self.frames) - 1, self.elapsed // self.frame_ticks)
        sx, sy, sw, sh = self.frames[idx]
        alpha = 1.0 if self.t > self.frame_ticks else max(0.0, self.t / self.frame_ticks)
        ctx.globalAlpha = alpha
        ctx.drawImage(img, sx, sy, sw, sh, self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)
        ctx.globalAlpha = 1.0


class FloatingText:
    def __init__(self, x, y, text, color="#7ceeff", life=52):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.t = life
        self.max_t = life

    def update(self):
        self.y -= 0.85
        self.t -= 1

    def draw(self):
        alpha = min(1.0, self.t / 18.0)
        ctx.save()
        ctx.globalAlpha = max(0.0, alpha)
        ctx.font = "800 15px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
        ctx.textAlign = "center"
        ctx.textBaseline = "middle"
        ctx.lineWidth = 3
        ctx.strokeStyle = "rgba(4, 10, 26, 0.85)"
        ctx.strokeText(self.text, self.x, self.y)
        ctx.fillStyle = self.color
        ctx.fillText(self.text, self.x, self.y)
        ctx.restore()


def add_effect(fx):
    if len(effects) >= MAX_EFFECTS:
        effects.pop(0)
    effects.append(fx)


def add_explosion(x, y, size=44, sparks=6, spark_color="#ffb347"):
    add_effect(Explosion(x, y, size=size))
    if sparks > 0:
        spawn_sparks(x, y, sparks, spark_color)


def add_ring(x, y, max_r, color, line_width=3.0, life=22):
    add_effect(RingWave(x, y, max_r, color, line_width=line_width, life=life))


def add_floating_text(x, y, text, color="#7ceeff"):
    if len(floating_texts) >= MAX_FLOATING_TEXTS:
        floating_texts.pop(0)
    floating_texts.append(FloatingText(x, y, text, color=color))


def spawn_sparks(x, y, count, color="#ffb347", speed_min=1.4, speed_max=4.6):
    for _ in range(count):
        if len(particles) >= MAX_PARTICLES:
            particles.pop(0)
        ang = randf(0, Math.PI * 2)
        spd = randf(speed_min, speed_max)
        particles.append(
            Particle(
                x,
                y,
                Math.cos(ang) * spd,
                Math.sin(ang) * spd,
                color,
                size=randf(1.8, 3.6),
                life=int(randf(14, 26)),
            )
        )


# ====== 游戏核心实体 ======
class Player:
    def __init__(self):
        self.w = 52
        self.h = 52
        self.x = max(0.0, canvas.width / 2 - self.w / 2)
        self.y = max(0.0, canvas.height - 120)
        self.speed = 4.6
        self.hp = 100
        self.weapon = "single"
        self.sprite_key = TIER_META["single"]["sprite"]
        self.shoot_cd = 0
        self.shield = 0
        self.invuln = 0
        self.clear_wave_timer = 0
        self.clear_wave_pulse_cd = 0
        self.alt_fire_cycle = 0
        self.tilt = 0.0
        self.prev_x = self.x

    def apply_weapon_tier(self, tier):
        self.weapon = tier
        self.sprite_key = TIER_META[tier]["sprite"]

    def update_motion(self, dx):
        target_tilt = clamp(dx * 0.025, -0.15, 0.15)
        self.tilt += (target_tilt - self.tilt) * 0.22

    def _draw_thrusters(self):
        meta = TIER_META[self.weapon]
        flicker = 1.0 + 0.28 * Math.sin(frame * 0.72) + randf(-0.1, 0.14)
        flame_len = 20.0 * flicker
        base_y = self.h * 0.44
        for ox in (-6.5, 6.5):
            # 外层等离子尾焰
            ctx.fillStyle = meta["flame_outer"]
            ctx.beginPath()
            ctx.moveTo(ox - 4.4, base_y)
            ctx.lineTo(ox + 4.4, base_y)
            ctx.lineTo(ox, base_y + flame_len)
            ctx.closePath()
            ctx.fill()
            # 白热内核
            ctx.fillStyle = meta["flame_inner"]
            ctx.beginPath()
            ctx.moveTo(ox - 2.1, base_y)
            ctx.lineTo(ox + 2.1, base_y)
            ctx.lineTo(ox, base_y + flame_len * 0.56)
            ctx.closePath()
            ctx.fill()

    def _draw_shield(self, cx, cy):
        if self.shield <= 0:
            return
        ratio = clamp(self.shield / SHIELD_DURATION, 0.0, 1.0)
        # 护盾剩余不足 1.5 秒时闪烁预警
        if self.shield < 90 and (frame // 5) % 2 == 0:
            base_alpha = 0.35
        else:
            base_alpha = 0.72 + 0.14 * Math.sin(frame * 0.18)

        shield_img = SPRITES.get("plane_shield")
        pulse = 1.0 + 0.04 * Math.sin(frame * 0.16)
        sw = self.w * 1.48 * pulse
        sh = self.h * 1.38 * pulse
        if _is_img_ready(shield_img):
            ctx.save()
            ctx.globalAlpha = base_alpha * 0.62
            ctx.drawImage(shield_img, cx - sw / 2, cy - sh / 2 - 2, sw, sh)
            ctx.restore()

        radius = self.w * 0.74
        ctx.save()
        # 底层能量淡环
        ctx.strokeStyle = "rgba(72, 236, 255, 0.24)"
        ctx.lineWidth = 2.5
        ctx.beginPath()
        ctx.arc(cx, cy, radius, 0, Math.PI * 2)
        ctx.stroke()

        # 剩余护盾进度弧
        ctx.strokeStyle = f"rgba(90, 245, 255, {base_alpha})"
        ctx.lineWidth = 3.2
        ctx.beginPath()
        start_ang = -Math.PI / 2
        ctx.arc(cx, cy, radius, start_ang, start_ang + Math.PI * 2 * ratio)
        ctx.stroke()
        ctx.restore()

    def draw(self):
        if self.hp <= 0:
            return
        if self.invuln > 0 and self.shield <= 0 and (self.invuln // 3) % 2 == 0:
            return

        cx = self.x + self.w / 2
        cy = self.y + self.h / 2

        ctx.save()
        ctx.translate(cx, cy)
        if abs(self.tilt) > 0.004:
            ctx.rotate(self.tilt)

        self._draw_thrusters()

        img = SPRITES.get(self.sprite_key)
        if _is_img_ready(img):
            ctx.drawImage(img, -self.w / 2, -self.h / 2, self.w, self.h)
        else:
            ctx.fillStyle = TIER_META[self.weapon]["inner"]
            ctx.fillRect(-self.w / 2, -self.h / 2, self.w, self.h)
        ctx.restore()

        self._draw_shield(cx, cy)

    def shoot(self):
        if self.shoot_cd > 0:
            return
        self.shoot_cd = 10
        play_sound("shoot", 0.22)
        self.alt_fire_cycle = (self.alt_fire_cycle + 1) % 8

        if len(bullets) >= MAX_BULLETS:
            return

        cx = self.x + self.w / 2
        tier = self.weapon

        # 红机 / 紫机每隔 8 轮释放高能激光束
        if tier != "single" and self.alt_fire_cycle == 0:
            bullets.append(
                Bullet(
                    cx - 5,
                    self.y - 26,
                    0,
                    -13.0,
                    "player",
                    bullet_type="laser",
                    w=10,
                    h=34,
                    damage=32,
                    ttl=52,
                    weapon_tier=tier,
                )
            )
            return

        if tier == "single":
            bullets.append(
                Bullet(cx - 3, self.y - 10, 0, -8.5, "player", damage=16, weapon_tier=tier)
            )
        elif tier == "twin":
            for ox, dx, dy in ((-10, -1.8, -8.4), (0, 0, -9.2), (10, 1.8, -8.4)):
                bullets.append(
                    Bullet(cx + ox - 3, self.y - 10, dx, dy, "player", damage=14, weapon_tier=tier)
                )
        else:
            for ox, dx, dy in (
                (-14, -3.0, -7.8),
                (-7, -1.5, -8.7),
                (0, 0, -9.5),
                (7, 1.5, -8.7),
                (14, 3.0, -7.8),
            ):
                bullets.append(
                    Bullet(cx + ox - 3, self.y - 10, dx, dy, "player", damage=12, weapon_tier=tier)
                )

    def hit(self, dmg):
        if self.invuln > 0:
            return False
        if self.shield > 0:
            self.shield = max(0, self.shield - int(dmg * 14))
            self.invuln = 10
            cx, cy = self.x + self.w / 2, self.y + self.h / 2
            add_ring(cx, cy, 48, "#5af5ff", line_width=2.5, life=14)
            spawn_sparks(cx, cy, 6, "#7ceeff")
            return False

        self.hp -= dmg
        self.invuln = PLAYER_INVULN_FRAMES
        idx = WEAPON_TIERS.index(self.weapon)
        if idx > 0:
            self.apply_weapon_tier(WEAPON_TIERS[idx - 1])
            add_floating_text(self.x + self.w / 2, self.y - 8, "火力降级", "#ff9e7d")
        return True


class Enemy:
    def __init__(self, kind="small"):
        spec = ENEMY_SPECS[kind]
        self.kind = kind
        self.w = spec["w"]
        self.h = spec["h"]
        self.sprite_key = spec["sprite"]
        self.score_value = spec["score"]
        self.x = randf(0, max(0, canvas.width - self.w))
        self.y = -self.h - randf(0, 90)
        spd_min, spd_max = get_diff_param("enemy_speed")
        self.vx = randf(-0.6, 0.6)
        self.vy = randf(spd_min, spd_max)
        self.hp = spec["hp"]
        self.max_hp = spec["hp"]
        self.cd = int(randf(32, 62))
        self.hit_flash = 0

    def draw(self):
        img = SPRITES.get(self.sprite_key)
        if _is_img_ready(img):
            ctx.drawImage(img, self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = "#c44" if self.kind == "small" else "#933"
            ctx.fillRect(self.x, self.y, self.w, self.h)

        # 受击闪光反馈
        if self.hit_flash > 0:
            ctx.save()
            ctx.globalAlpha = 0.45
            ctx.fillStyle = "#ffffff"
            ctx.beginPath()
            ctx.arc(self.x + self.w / 2, self.y + self.h / 2, self.w * 0.44, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()

        # 中/大型敌机受损后展示简洁血条
        if self.kind != "small" and 0 < self.hp < self.max_hp:
            bar_w = self.w * 0.76
            bar_x = self.x + (self.w - bar_w) / 2
            bar_y = self.y - 7
            ctx.fillStyle = "rgba(0, 0, 0, 0.55)"
            ctx.fillRect(bar_x, bar_y, bar_w, 4)
            ctx.fillStyle = "#ff6b6b"
            ctx.fillRect(bar_x, bar_y, bar_w * (self.hp / self.max_hp), 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x <= 0 or self.x + self.w >= canvas.width:
            self.vx = -self.vx
            self.x = clamp(self.x, 0, canvas.width - self.w)

        if self.hit_flash > 0:
            self.hit_flash -= 1

        self.cd -= 1
        if self.cd > 0 or self.y < 10:
            return

        self.cd = int(90 - 30 * randf(0, 1))
        if Math.random() >= get_diff_param("bullet_rate"):
            return
        if len(bullets) >= MAX_BULLETS:
            return

        tx = player.x + player.w / 2
        ty = player.y + player.h / 2
        cx = self.x + self.w / 2
        cy = self.y + self.h
        vx = tx - cx
        vy = ty - cy
        mag = Math.sqrt(vx * vx + vy * vy) + 1e-5
        vx, vy = vx / mag * 3.0, vy / mag * 3.0

        if self.kind == "small":
            bullets.append(
                Bullet(cx - 5, cy, vx, vy, "enemy", w=12, h=12, damage=14)
            )
        elif self.kind == "medium":
            base_ang = Math.atan2(vy, vx)
            for off in (-0.34, 0.0, 0.34):
                if len(bullets) >= MAX_BULLETS:
                    break
                ang = base_ang + off
                bullets.append(
                    Bullet(
                        cx - 7,
                        cy,
                        3.0 * Math.cos(ang),
                        3.0 * Math.sin(ang),
                        "enemy",
                        sprite_key="boss_bullet_triangle",
                        w=14,
                        h=14,
                        damage=12,
                    )
                )
        else:
            bullets.append(
                Bullet(
                    cx - 6,
                    cy,
                    vx * 0.9,
                    vy * 0.9 + 0.35,
                    "enemy",
                    bullet_type="orb",
                    sprite_key="boss_bullet_hellfire_yellow",
                    w=12,
                    h=24,
                    damage=18,
                )
            )
            if len(bullets) < MAX_BULLETS and Math.random() < 0.35:
                bullets.append(
                    Bullet(
                        cx - 7,
                        cy,
                        vx * 0.65,
                        vy * 0.65,
                        "enemy",
                        bullet_type="homing",
                        sprite_key="boss_bullet_thunderball_red",
                        w=15,
                        h=15,
                        damage=16,
                        homing=True,
                        speed=3.2,
                        turn_rate=0.18,
                    )
                )


class Boss:
    def __init__(self):
        size = int(clamp(canvas.width * 0.38, 120, 158))
        self.w = size
        self.h = size
        self.x = max(0.0, canvas.width / 2 - self.w / 2)
        self.y = -self.h
        self.target_y = 94
        self.vy = 1.6
        self.vx = 2.1
        self.hp = get_diff_param("boss_hp")
        self.max_hp = self.hp
        self.phase = 0
        self.cd = 100
        self.pattern_count = 0
        self.hit_flash = 0
        self.warning_timer = 110

    def is_enraged(self):
        return self.hp <= self.max_hp * 0.45

    def draw(self):
        enraged = self.is_enraged()
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2

        # 狂暴状态底层危险光环
        if enraged:
            pulse = 0.24 + 0.14 * Math.sin(frame * 0.24)
            ctx.save()
            ctx.globalAlpha = pulse
            ctx.fillStyle = "#ff2e4c"
            ctx.beginPath()
            ctx.arc(cx, cy, self.w * 0.56, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()

        # 正确裁切 bossplane_crazy.png（200x400 纵向 2 帧，每帧 200x200）
        crazy_img = SPRITES.get("boss_crazy")
        normal_img = SPRITES.get("boss")
        if (enraged or self.phase >= 2) and _is_img_ready(crazy_img):
            frame_idx = (frame // 8) % 2
            ctx.drawImage(crazy_img, 0, frame_idx * 200, 200, 200, self.x, self.y, self.w, self.h)
        elif _is_img_ready(normal_img):
            ctx.drawImage(normal_img, self.x, self.y, self.w, self.h)
        else:
            ctx.fillStyle = "#6228ba"
            ctx.fillRect(self.x, self.y, self.w, self.h)

        if self.hit_flash > 0:
            ctx.save()
            ctx.globalAlpha = 0.28
            ctx.fillStyle = "#ffffff"
            ctx.beginPath()
            ctx.arc(cx, cy, self.w * 0.42, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()

    def draw_overlay_ui(self):
        # 居中顶部 Boss 血条（位于 y=70，留出充裕间距避开左上 HUD 与右上控制按钮）
        bar_w = min(400, canvas.width - 36)
        bar_h = 12
        bar_x = (canvas.width - bar_w) / 2
        bar_y = 70
        ratio = clamp(self.hp / self.max_hp, 0.0, 1.0)
        enraged = self.is_enraged()

        ctx.save()
        # 背景槽
        ctx.fillStyle = "rgba(6, 12, 28, 0.78)"
        ctx.fillRect(bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6)
        ctx.strokeStyle = "rgba(255, 92, 118, 0.62)" if enraged else "rgba(110, 215, 255, 0.45)"
        ctx.lineWidth = 1.5
        ctx.strokeRect(bar_x - 3, bar_y - 3, bar_w + 6, bar_h + 6)

        # 渐变血条填充
        if ratio > 0:
            grad = ctx.createLinearGradient(bar_x, bar_y, bar_x + bar_w, bar_y)
            if enraged:
                grad.addColorStop(0.0, "#ff1e56")
                grad.addColorStop(1.0, "#ff9a3c")
            else:
                grad.addColorStop(0.0, "#e11d48")
                grad.addColorStop(0.65, "#f97316")
                grad.addColorStop(1.0, "#facc15")
            ctx.fillStyle = grad
            ctx.fillRect(bar_x, bar_y, bar_w * ratio, bar_h)

            # 顶部高光细线
            ctx.fillStyle = "rgba(255, 255, 255, 0.28)"
            ctx.fillRect(bar_x, bar_y, bar_w * ratio, 3)

        # 标签文字
        ctx.font = "800 11px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
        ctx.textAlign = "left"
        ctx.textBaseline = "bottom"
        ctx.fillStyle = "#ff8598" if enraged else "#cbeeff"
        tag = "BOSS · 狂暴阶段" if enraged else "BOSS · 旗舰首领"
        ctx.fillText(tag, bar_x, bar_y - 5)

        ctx.textAlign = "right"
        ctx.fillStyle = "rgba(255, 255, 255, 0.85)"
        ctx.fillText(f"{int(Math.ceil(ratio * 100))}%", bar_x + bar_w, bar_y - 5)
        ctx.restore()

        # Boss 出场警示横幅
        if self.warning_timer > 0:
            alpha = min(1.0, self.warning_timer / 24.0) * (0.68 + 0.32 * Math.sin(frame * 0.45))
            banner_y = canvas.height * 0.34
            ctx.save()
            ctx.globalAlpha = alpha
            ctx.fillStyle = "rgba(180, 16, 40, 0.34)"
            ctx.fillRect(0, banner_y - 26, canvas.width, 52)
            ctx.fillStyle = "rgba(255, 76, 98, 0.85)"
            ctx.fillRect(0, banner_y - 26, canvas.width, 2)
            ctx.fillRect(0, banner_y + 24, canvas.width, 2)
            ctx.font = "900 22px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillStyle = "#ffe4e6"
            ctx.fillText("⚠  WARNING · 旗舰首领来袭  ⚠", canvas.width / 2, banner_y)
            ctx.restore()

    def update(self):
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.warning_timer > 0:
            self.warning_timer -= 1

        if self.y < self.target_y:
            self.y += self.vy
        else:
            speed_mul = 1.28 if self.is_enraged() else 1.0
            self.x += self.vx * speed_mul
            if self.x <= 8 or self.x + self.w >= canvas.width - 8:
                self.vx = -self.vx
                self.x = clamp(self.x, 8, canvas.width - self.w - 8)

        self.cd -= 1
        if self.cd <= 0:
            self.pattern_count += 1
            base_cd = 64 if self.is_enraged() else 78
            self.cd = max(44, base_cd - self.pattern_count)
            self.phase = (self.phase + 1) % 4
            self.fire_pattern(self.phase)

    def fire_pattern(self, pattern):
        if len(bullets) >= MAX_BULLETS:
            return
        cx = self.x + self.w / 2
        cy = self.y + self.h - 10

        if pattern == 0:
            # 扇形炎弹
            for deg in range(-44, 45, 11):
                if len(bullets) >= MAX_BULLETS:
                    break
                rad = (deg / 180.0) * Math.PI
                vx, vy = 3.1 * Math.sin(rad), 3.1 * Math.cos(rad)
                bullets.append(
                    Bullet(cx - 6, cy, vx, vy, "enemy", sprite_key="boss_bullet_default", w=12, h=20, damage=14)
                )
        elif pattern == 1:
            # 锁定连发雷球
            tx, ty = player.x + player.w / 2, player.y + player.h / 2
            base_ang = Math.atan2(ty - cy, tx - cx)
            for k in range(11):
                if len(bullets) >= MAX_BULLETS:
                    break
                ang = base_ang + (k - 5) * 0.085
                vx, vy = 3.3 * Math.cos(ang), 3.3 * Math.sin(ang)
                sk = "boss_bullet_thunderball_red" if k % 2 == 0 else "boss_bullet_thunderball_green"
                bullets.append(
                    Bullet(cx - 7, cy, vx, vy, "enemy", sprite_key=sk, w=15, h=15, damage=14)
                )
        elif pattern == 2:
            # 日冕螺旋弹幕
            offset = randf(0, 0.5)
            for k in range(22):
                if len(bullets) >= MAX_BULLETS:
                    break
                ang = k * (Math.PI * 2 / 22) + offset
                vx, vy = 2.6 * Math.cos(ang), 2.6 * Math.sin(ang) + 0.75
                bullets.append(
                    Bullet(
                        cx - 7,
                        cy,
                        vx,
                        vy,
                        "enemy",
                        sprite_key="boss_bullet_sun_particle",
                        bullet_type="orb",
                        w=15,
                        h=15,
                        damage=14,
                    )
                )
        else:
            # 混合弹幕：四轨烈焰光束 + 双侧追踪雷球
            for lane in (-44, -18, 18, 44):
                if len(bullets) >= MAX_BULLETS:
                    break
                bullets.append(
                    Bullet(
                        cx + lane - 6,
                        cy,
                        0,
                        6.4,
                        "enemy",
                        bullet_type="hellfire",
                        sprite_key="boss_bullet_hellfire_red",
                        w=14,
                        h=34,
                        damage=20,
                    )
                )
            for side in (-52, 52):
                if len(bullets) >= MAX_BULLETS:
                    break
                bullets.append(
                    Bullet(
                        cx + side - 8,
                        cy + 4,
                        0,
                        3.1,
                        "enemy",
                        bullet_type="homing",
                        sprite_key="boss_bullet_thunderball_green",
                        w=16,
                        h=16,
                        damage=18,
                        homing=True,
                        speed=3.4,
                        turn_rate=0.15,
                    )
                )


class Bullet:
    # 指向性子弹精灵朝向校准偏移量
    _UP_TIP_SPRITES = ("boss_bullet_hellfire_red", "boss_bullet_hellfire_yellow")
    _DOWN_TIP_SPRITES = ("boss_bullet_default",)
    _SPIN_SPRITES = (
        "boss_bullet_triangle",
        "boss_bullet_thunderball_red",
        "boss_bullet_thunderball_green",
    )

    def __init__(
        self,
        x,
        y,
        vx,
        vy,
        owner,
        sprite_key=None,
        w=None,
        h=None,
        homing=False,
        speed=None,
        bullet_type="normal",
        damage=12,
        ttl=0,
        turn_rate=0.4,
        weapon_tier=None,
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.w = w or 6
        self.h = h or 14
        self.owner = owner
        self.sprite_key = sprite_key
        self.homing = homing
        self.bullet_type = bullet_type
        self.damage = damage
        self.ttl = ttl
        self.turn_rate = turn_rate
        # 锁定发射时的武器阶层，避免后续换枪导致空中子弹变色
        self.weapon_tier = weapon_tier or (player.weapon if owner == "player" else "single")
        vlen = Math.sqrt(vx * vx + vy * vy)
        self.speed = speed or (vlen or 7.0)
        self.age = 0

    def _draw_player_laser(self):
        meta = TIER_META[self.weapon_tier]
        cx = self.x + self.w / 2
        # 无 shadowBlur 多层霓虹叠加，视觉锐利且高性能
        ctx.fillStyle = meta["outer"]
        ctx.fillRect(self.x - 4, self.y - 4, self.w + 8, self.h + 8)
        ctx.fillStyle = meta["inner"]
        ctx.fillRect(self.x, self.y, self.w, self.h)
        ctx.fillStyle = "#ffffff"
        ctx.fillRect(cx - 2, self.y + 2, 4, max(4, self.h - 4))

    def _draw_player_bolt(self):
        meta = TIER_META[self.weapon_tier]
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2
        ctx.fillStyle = meta["outer"]
        ctx.beginPath()
        ctx.ellipse(cx, cy + 2, self.w * 0.95, self.h * 0.82, 0, 0, Math.PI * 2)
        ctx.fill()

        ctx.fillStyle = meta["inner"]
        ctx.beginPath()
        ctx.ellipse(cx, cy, self.w * 0.56, self.h * 0.58, 0, 0, Math.PI * 2)
        ctx.fill()

        ctx.fillStyle = meta["core"]
        ctx.fillRect(cx - 1.1, self.y + 1.5, 2.2, max(4, self.h - 3))

    def draw(self):
        if self.owner == "player":
            if self.bullet_type == "laser":
                self._draw_player_laser()
            else:
                self._draw_player_bolt()
            return

        img = SPRITES.get(self.sprite_key) if self.sprite_key else SPRITES.get("enemy_bullet")
        if not _is_img_ready(img):
            ctx.fillStyle = "#ff9933"
            ctx.beginPath()
            ctx.arc(self.x + self.w / 2, self.y + self.h / 2, max(self.w, self.h) * 0.45, 0, Math.PI * 2)
            ctx.fill()
            return

        cx = self.x + self.w / 2
        cy = self.y + self.h / 2

        if self.sprite_key in self._UP_TIP_SPRITES:
            rot = Math.atan2(self.vy, self.vx) + Math.PI / 2
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(rot)
            ctx.drawImage(img, -self.w / 2, -self.h / 2, self.w, self.h)
            ctx.restore()
        elif self.sprite_key in self._DOWN_TIP_SPRITES:
            rot = Math.atan2(self.vy, self.vx) - Math.PI / 2
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(rot)
            ctx.drawImage(img, -self.w / 2, -self.h / 2, self.w, self.h)
            ctx.restore()
        elif self.sprite_key in self._SPIN_SPRITES:
            ctx.save()
            ctx.translate(cx, cy)
            ctx.rotate(self.age * 0.16)
            ctx.drawImage(img, -self.w / 2, -self.h / 2, self.w, self.h)
            ctx.restore()
        else:
            ctx.drawImage(img, self.x, self.y, self.w, self.h)

    def update(self):
        self.age += 1
        if self.homing and player.hp > 0:
            target = player if self.owner == "enemy" else boss
            if target is not None:
                dx = (target.x + target.w / 2) - (self.x + self.w / 2)
                dy = (target.y + target.h / 2) - (self.y + self.h / 2)
                dist = Math.sqrt(dx * dx + dy * dy) or 1.0
                desired_vx = dx / dist * self.speed
                desired_vy = dy / dist * self.speed
                self.vx = self.vx * (1.0 - self.turn_rate) + desired_vx * self.turn_rate
                self.vy = self.vy * (1.0 - self.turn_rate) + desired_vy * self.turn_rate

        if self.bullet_type == "orb":
            self.vx *= 0.997
            self.vy *= 1.004

        self.x += self.vx
        self.y += self.vy
        if self.ttl > 0:
            self.ttl -= 1


class PowerUp:
    _GLOW_STYLES = {
        "weapon": ("rgba(196, 98, 255, 0.28)", "#d975ff"),
        "shield": ("rgba(45, 240, 210, 0.28)", "#42f5d4"),
        "heal": ("rgba(255, 118, 72, 0.28)", "#ff8a5b"),
    }

    def __init__(self, kind, x, y):
        self.kind = kind  # weapon | shield | heal
        self.w = 34
        self.h = 34
        self.x = clamp(x - self.w / 2, 12, canvas.width - self.w - 12)
        self.y = y
        self.vy = 1.95
        self.phase = randf(0, Math.PI * 2)

    def _resolve_sprite(self):
        if self.kind == "weapon":
            if player.weapon == "single":
                return SPRITES.get("power_weapon_red")
            return SPRITES.get("power_weapon_purple")
        if self.kind == "shield":
            return SPRITES.get("plane_shield")
        return SPRITES.get("power_heal")

    def draw(self):
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2
        pulse = 1.0 + 0.08 * Math.sin(frame * 0.14 + self.phase)
        fill_glow, ring_color = self._GLOW_STYLES[self.kind]
        if self.kind == "weapon" and player.weapon == "single":
            fill_glow, ring_color = "rgba(255, 110, 62, 0.30)", "#ff7e47"

        # 呼吸能量光环
        ctx.save()
        ctx.fillStyle = fill_glow
        ctx.beginPath()
        ctx.arc(cx, cy, self.w * 0.68 * pulse, 0, Math.PI * 2)
        ctx.fill()

        ctx.strokeStyle = ring_color
        ctx.lineWidth = 1.8
        ctx.beginPath()
        ctx.arc(cx, cy, self.w * 0.56 * pulse, 0, Math.PI * 2)
        ctx.stroke()

        # 护盾道具使用徽章底盘，使三类道具轮廓统一精致
        if self.kind == "shield":
            ctx.fillStyle = "rgba(6, 36, 44, 0.82)"
            ctx.beginPath()
            ctx.arc(cx, cy, self.w * 0.46, 0, Math.PI * 2)
            ctx.fill()

        img = self._resolve_sprite()
        if _is_img_ready(img):
            draw_w = self.w * (0.82 if self.kind == "shield" else 0.96) * pulse
            draw_h = self.h * (0.72 if self.kind == "shield" else 0.96) * pulse
            ctx.drawImage(img, cx - draw_w / 2, cy - draw_h / 2, draw_w, draw_h)
        else:
            ctx.fillStyle = ring_color
            ctx.fillRect(self.x + 4, self.y + 4, self.w - 8, self.h - 8)
        ctx.restore()

    def update(self):
        self.y += self.vy
        self.x = clamp(
            self.x + Math.sin(frame * 0.08 + self.phase) * 0.6,
            8,
            canvas.width - self.w - 8,
        )

        # 接近玩家战机时产生轻柔磁吸吸附
        if player.hp > 0:
            px, py = player.x + player.w / 2, player.y + player.h / 2
            cx, cy = self.x + self.w / 2, self.y + self.h / 2
            dx, dy = px - cx, py - cy
            d2 = dx * dx + dy * dy
            if 1.0 < d2 < 96 * 96:
                dist = Math.sqrt(d2)
                pull = 3.8 * (1.0 - dist / 96.0) + 1.2
                self.x += dx / dist * pull
                self.y += dy / dist * pull


# ====== HUD 同步与菜单记录 ======
_hud_last = {}


def _set_text_cached(el, key, text):
    if el is not None and _hud_last.get(key) != text:
        _hud_last[key] = text
        el.textContent = text


def update_hud():
    int_score = int(score)
    hp_val = max(0, int(player.hp))
    tier_meta = TIER_META[player.weapon]
    diff_zh = DIFF_NAME_ZH.get(selected_diff, selected_diff)
    dyn_tier = get_difficulty_tier(int_score)

    _set_text_cached(score_el, "score", str(int_score))
    _set_text_cached(lives_el, "lives", str(hp_val))
    _set_text_cached(level_el, "level", f"{diff_zh} · 动态+{dyn_tier}")

    badge_text = f"{tier_meta['label']} · 护盾" if player.shield > 0 else tier_meta["label"]
    _set_text_cached(weapon_badge_el, "weapon_text", badge_text)
    if weapon_badge_el is not None and _hud_last.get("weapon_tier") != player.weapon:
        _hud_last["weapon_tier"] = player.weapon
        weapon_badge_el.setAttribute("data-tier", player.weapon)

    if hp_bar_el is not None and _hud_last.get("hp_pct") != hp_val:
        _hud_last["hp_pct"] = hp_val
        hp_bar_el.style.width = f"{clamp(hp_val, 0, 100)}%"

    if hp_wrap_el is not None:
        is_low = hp_val <= 30
        if _hud_last.get("hp_low") != is_low:
            _hud_last["hp_low"] = is_low
            hp_wrap_el.classList.toggle("low", is_low)
        has_shield = player.shield > 0
        if _hud_last.get("hp_shield") != has_shield:
            _hud_last["hp_shield"] = has_shield
            hp_wrap_el.classList.toggle("shielded", has_shield)


def update_menu_records(last_run_score=None):
    if best_score <= 0 and last_run_score is None:
        return
    if best_score_val_el is not None:
        best_score_val_el.textContent = str(int(best_score))
    if menu_record_el is not None:
        menu_record_el.hidden = False
    if last_run_score is not None:
        if last_score_val_el is not None:
            last_score_val_el.textContent = str(int(last_run_score))
        if last_score_sep_el is not None:
            last_score_sep_el.hidden = False
        if last_score_wrap_el is not None:
            last_score_wrap_el.hidden = False


# ====== 生成与战斗事件 ======
def spawn_enemy():
    if len(enemies) >= MAX_ENEMIES:
        return
    r = Math.random()
    kind = "small" if r < 0.55 else ("medium" if r < 0.85 else "big")
    enemies.append(Enemy(kind))


def spawn_power(x, y):
    if len(powers) >= MAX_POWERS:
        return
    r = Math.random()
    kind = "weapon" if r < 0.5 else ("shield" if r < 0.8 else "heal")
    powers.append(PowerUp(kind, x, y))


def trigger_clear_wave():
    player.clear_wave_timer = CLEAR_WAVE_DURATION
    player.clear_wave_pulse_cd = 0
    px, py = player.x + player.w / 2, player.y + player.h / 2
    add_ring(px, py, max(canvas.width, canvas.height) * 0.45, "#67e8f9", line_width=5.0, life=28)
    add_ring(px, py, max(canvas.width, canvas.height) * 0.30, "#c084fc", line_width=3.5, life=22)


def _defeat_boss():
    global boss, score, spawn_boss_at, shake
    score += 300
    bx, by = boss.x + boss.w / 2, boss.y + boss.h / 2
    bw, bh = boss.w, boss.h

    # 使用 bossplane_bomb.png 纵向 5 帧解体爆炸动画（200x1000 -> 每帧 200x200）
    bomb_frames = [(0, i * 200, 200, 200) for i in range(5)]
    add_effect(SpriteAnim(bx, by, bw * 1.15, bh * 1.15, "boss_bomb", bomb_frames, frame_ticks=6))
    add_ring(bx, by, 180, "#ffaa33", line_width=5.0, life=28)
    add_ring(bx, by, 120, "#fff0a8", line_width=3.5, life=20)
    add_explosion(bx, by, size=125, sparks=22, spark_color="#ffd166")
    for ox, oy in ((-46, -24), (42, -26), (-36, 30), (48, 22), (0, -48)):
        add_explosion(bx + ox, by + oy, size=66, sparks=5, spark_color="#ff6b4a")
    add_floating_text(bx, by - 20, "BOSS 击毁 +300", "#fde047")

    play_sound("bigboom", 0.65)
    shake = max(shake, 18)
    boss = None
    spawn_boss_at = score + BOSS_SCORE_INTERVAL


def run_clear_wave():
    global shake, score
    if player.clear_wave_timer <= 0:
        return
    player.clear_wave_timer -= 1
    player.clear_wave_pulse_cd -= 1
    if player.clear_wave_pulse_cd > 0:
        return

    player.clear_wave_pulse_cd = CLEAR_WAVE_PULSE_GAP
    shake = max(shake, 10)
    play_sound("boom3", 0.18)

    px, py = player.x + player.w / 2, player.y + player.h / 2
    add_ring(px, py, 210, "#5ce1ff", line_width=3.2, life=16)

    for e in list(enemies):
        add_explosion(e.x + e.w / 2, e.y + e.h / 2, size=46, sparks=4, spark_color="#7ceeff")
        score += e.score_value
        safe_remove(enemies, e)

    for eb in [b for b in bullets if b.owner == "enemy"]:
        spawn_sparks(eb.x + eb.w / 2, eb.y + eb.h / 2, 2, "#7ceeff", speed_min=0.8, speed_max=2.4)
        safe_remove(bullets, eb)

    if boss is not None:
        boss.hp -= 90
        boss.hit_flash = 4
        score += 10
        if boss.hp <= 0:
            _defeat_boss()


def maybe_spawn_boss():
    global boss
    if boss is None and score >= spawn_boss_at:
        boss = Boss()


def _player_center_hit(obj, radius=PLAYER_HIT_RADIUS):
    px = player.x + player.w / 2
    py = player.y + player.h / 2
    ox = obj.x + obj.w / 2
    oy = obj.y + obj.h / 2
    dx = ox - px
    dy = oy - py
    # 大型敌机与 Boss 按自身体积扩充合理碰撞半径
    extra = min(obj.w, obj.h) * 0.28
    hit_r = radius + extra
    return dx * dx + dy * dy <= hit_r * hit_r


def _apply_powerup(p):
    global score
    play_sound("pickup", 0.36)
    px = player.x + player.w / 2
    py = player.y + player.h / 2

    if p.kind == "weapon":
        if player.weapon == "single":
            player.apply_weapon_tier("twin")
            add_ring(px, py, 64, "#ff684f", line_width=3.2, life=20)
            spawn_sparks(px, py, 12, "#ff8b66")
            add_floating_text(px, py - 24, "火力升级 · 赤炎三联", "#ff9e80")
        elif player.weapon == "twin":
            player.apply_weapon_tier("spread")
            add_ring(px, py, 72, "#d875ff", line_width=3.6, life=22)
            spawn_sparks(px, py, 14, "#e39eff")
            add_floating_text(px, py - 24, "火力全开 · 紫电散射", "#ebadff")
        else:
            trigger_clear_wave()
            spawn_sparks(px, py, 16, "#67e8f9")
            add_floating_text(px, py - 26, "电磁脉冲清屏激活！", "#67e8f9")
    elif p.kind == "shield":
        player.shield = SHIELD_DURATION
        add_ring(px, py, 68, "#42f5d4", line_width=3.2, life=20)
        spawn_sparks(px, py, 12, "#6cfce2")
        add_floating_text(px, py - 24, "能量护盾激活", "#6cfce2")
    else:
        if player.hp >= 100:
            score += 100
            add_ring(px, py, 60, "#fde047", line_width=3.0, life=18)
            spawn_sparks(px, py, 10, "#fde047")
            add_floating_text(px, py - 24, "满装甲奖励 +100", "#fde047")
        else:
            healed = min(30, 100 - player.hp)
            player.hp = min(100, player.hp + 30)
            add_ring(px, py, 60, "#34d399", line_width=3.0, life=18)
            spawn_sparks(px, py, 10, "#6ee7b7")
            add_floating_text(px, py - 24, f"装甲修复 +{int(healed)}", "#6ee7b7")


# ====== 游戏状态与主循环 ======
selected_diff = "normal"
state = "menu"  # menu | playing | gameover
paused = False
best_score = _load_best_score()
last_is_new_record = False

player = None
enemies = []
bullets = []
powers = []
effects = []
particles = []
floating_texts = []
boss = None

score = 0.0
frame = 0
shake = 0
spawn_boss_at = INITIAL_BOSS_SCORE
death_timer = 0

_raf_id = None
_last_ts = None
_accum_ms = 0.0
_gameover_timer_id = None

keys = {
    "ArrowLeft": False,
    "ArrowRight": False,
    "ArrowUp": False,
    "ArrowDown": False,
    "KeyA": False,
    "KeyD": False,
    "KeyW": False,
    "KeyS": False,
}
pointer_active = False
active_pointer_id = None


def reset_input():
    global pointer_active, active_pointer_id
    for k in keys:
        keys[k] = False
    pointer_active = False
    active_pointer_id = None


def reset_game():
    global player, boss, score, frame, shake, spawn_boss_at, death_timer, paused, last_is_new_record
    player = Player()
    player.x = clamp(player.x, 0, canvas.width - player.w)
    player.y = clamp(player.y, 0, canvas.height - player.h)
    player.prev_x = player.x
    enemies.clear()
    bullets.clear()
    powers.clear()
    effects.clear()
    particles.clear()
    floating_texts.clear()
    boss = None
    score = 0.0
    frame = 0
    shake = 0
    spawn_boss_at = INITIAL_BOSS_SCORE
    death_timer = 0
    paused = False
    last_is_new_record = False
    _hud_last.clear()
    reset_input()
    document.body.classList.remove("paused")
    _sync_pause_button()
    update_hud()


def _step_playing():
    global frame, score, shake, death_timer

    step_background(1.0)

    if player.hp > 0:
        move_x = (keys["ArrowRight"] or keys["KeyD"]) - (keys["ArrowLeft"] or keys["KeyA"])
        move_y = (keys["ArrowDown"] or keys["KeyS"]) - (keys["ArrowUp"] or keys["KeyW"])
        if move_x and move_y:
            inv = 0.70710678
            dx = move_x * player.speed * inv
            dy = move_y * player.speed * inv
        else:
            dx = move_x * player.speed
            dy = move_y * player.speed

        if dx != 0 or dy != 0:
            player.x = clamp(player.x + dx, 0, canvas.width - player.w)
            player.y = clamp(player.y + dy, 0, canvas.height - player.h)

        player.update_motion(player.x - player.prev_x)
        player.prev_x = player.x
        player.shoot()

    if player.shoot_cd > 0:
        player.shoot_cd -= 1
    if player.shield > 0:
        player.shield -= 1
    if player.invuln > 0:
        player.invuln -= 1

    run_clear_wave()
    maybe_spawn_boss()

    if boss is not None:
        boss.update()

    # 敌机刷怪逻辑
    if Math.random() < get_diff_param("enemy_rate"):
        if boss is None:
            spawn_enemy()
        elif selected_diff == "normal":
            if len(enemies) < MAX_ENEMIES:
                enemies.append(Enemy("small"))
        elif selected_diff == "hard":
            spawn_enemy()

    # 更新敌机
    for e in list(enemies):
        e.update()
        if e.y > canvas.height + 50:
            safe_remove(enemies, e)

    # 更新子弹
    for b in list(bullets):
        b.update()
        if b.bullet_type == "laser" and b.ttl <= 0:
            safe_remove(bullets, b)
            continue
        if b.y < -60 or b.y > canvas.height + 60 or b.x < -60 or b.x > canvas.width + 60:
            safe_remove(bullets, b)

    # 更新道具
    for p in list(powers):
        p.update()
        if p.y > canvas.height + 50:
            safe_remove(powers, p)

    # 玩家子弹碰撞检测（严格防止已销毁子弹二次命中 Boss）
    for b in list(bullets):
        if b.owner != "player":
            continue
        hit_enemy = False
        for e in list(enemies):
            if rects_collide(b, e):
                hit_enemy = True
                safe_remove(bullets, b)
                e.hp -= b.damage
                e.hit_flash = 3
                spawn_sparks(b.x + b.w / 2, b.y, 4, TIER_META[b.weapon_tier]["inner"], 1.0, 3.2)
                if e.hp <= 0:
                    add_explosion(e.x + e.w / 2, e.y + e.h / 2, size=max(e.w, e.h) * 1.15, sparks=8)
                    play_sound("boom", 0.24)
                    score += e.score_value
                    if Math.random() < 0.25:
                        spawn_power(e.x + e.w / 2, e.y + e.h / 2)
                    safe_remove(enemies, e)
                else:
                    play_sound("boom", 0.14)
                break
        if hit_enemy:
            continue

        if boss is not None and rects_collide(b, boss):
            safe_remove(bullets, b)
            boss.hp -= b.damage
            boss.hit_flash = 3
            score += 2
            spawn_sparks(b.x + b.w / 2, b.y, 4, "#ffd166", 1.2, 3.5)
            play_sound("boom2", 0.22)
            if boss.hp <= 0:
                _defeat_boss()

    # 敌方子弹撞击玩家
    if player.hp > 0:
        for b in list(bullets):
            if b.owner != "enemy":
                continue
            if _player_center_hit(b):
                damaged = player.hit(b.damage)
                safe_remove(bullets, b)
                if damaged:
                    add_explosion(player.x + player.w / 2, player.y + player.h / 2, size=50, sparks=8, spark_color="#ff6b6b")
                    play_sound("boom", 0.28)
                    shake = max(shake, 8)

    # 敌机与 Boss 机体撞击玩家
    if player.hp > 0:
        for e in list(enemies):
            if _player_center_hit(e):
                damaged = player.hit(25)
                add_explosion(e.x + e.w / 2, e.y + e.h / 2, size=54, sparks=8)
                safe_remove(enemies, e)
                if damaged:
                    play_sound("boom", 0.28)
                    shake = max(shake, 10)

        if boss is not None and _player_center_hit(boss, radius=18):
            damaged = player.hit(28)
            if damaged:
                add_explosion(player.x + player.w / 2, player.y + player.h / 2, size=56, sparks=10, spark_color="#ff5555")
                play_sound("boom", 0.30)
                shake = max(shake, 12)

    # 道具拾取检测
    if player.hp > 0:
        for p in list(powers):
            if rects_collide(p, player):
                _apply_powerup(p)
                safe_remove(powers, p)

    # 更新视觉特效
    for fx in list(effects):
        fx.update()
        if fx.t <= 0:
            safe_remove(effects, fx)

    for pt in list(particles):
        pt.update()
        if pt.life <= 0:
            safe_remove(particles, pt)

    for ft in list(floating_texts):
        ft.update()
        if ft.t <= 0:
            safe_remove(floating_texts, ft)

    if shake > 0:
        shake -= 1

    frame += 1
    if player.hp > 0:
        score += 0.03
    update_hud()

    # 玩家坠机连环爆炸演出（裁切 myplaneexplosion.png 对应涂装 2 帧）
    if player.hp <= 0:
        if death_timer == 0:
            px, py = player.x + player.w / 2, player.y + player.h / 2
            col = TIER_META[player.weapon]["explosion_col"]
            p_frames = [(col * 50, 0, 50, 50), ((col + 1) * 50, 0, 50, 50)]
            add_effect(SpriteAnim(px, py, 64, 64, "player_explosion", p_frames, frame_ticks=8))
            add_ring(px, py, 96, "#ff6b4a", line_width=4.0, life=24)
            add_explosion(px, py, size=92, sparks=18, spark_color="#ff9944")
            for ox, oy in ((-22, -12), (20, -16), (-6, 18), (14, 10)):
                add_explosion(px + ox, py + oy, size=48, sparks=4, spark_color="#ff7744")
            shake = 18
            play_sound("bigboom", 0.62)
            death_timer = 52
        else:
            death_timer -= 1
            if Math.random() < 0.28:
                add_explosion(
                    player.x + randf(0, player.w),
                    player.y + randf(0, player.h),
                    size=42,
                    sparks=3,
                )
            if death_timer <= 0:
                death_timer = 0
                end_game()


def _draw_clear_wave_aura():
    if player.clear_wave_timer <= 0:
        return
    px = player.x + player.w / 2
    py = player.y + player.h / 2
    alpha = 0.28 + 0.18 * Math.sin(frame * 0.35)
    radius = 74 + 18 * Math.sin(frame * 0.28)
    ctx.save()
    ctx.strokeStyle = f"rgba(103, 232, 249, {alpha})"
    ctx.lineWidth = 3.5
    ctx.beginPath()
    ctx.arc(px, py, radius, 0, Math.PI * 2)
    ctx.stroke()

    ctx.strokeStyle = f"rgba(192, 132, 252, {alpha * 0.85})"
    ctx.lineWidth = 2.0
    ctx.beginPath()
    ctx.arc(px, py, radius * 0.72, 0, Math.PI * 2)
    ctx.stroke()

    # 画面四边轻微青蓝充能提示框
    ctx.strokeStyle = f"rgba(0, 220, 255, {0.14 + 0.08 * Math.sin(frame * 0.22)})"
    ctx.lineWidth = 8
    ctx.strokeRect(0, 0, canvas.width, canvas.height)
    ctx.restore()


def _draw_gameover_overlay():
    ctx.save()
    ctx.fillStyle = "rgba(3, 7, 18, 0.56)"
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    cx = canvas.width / 2
    cy = canvas.height / 2

    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.font = "900 46px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    ctx.fillStyle = "#ff4d5a"
    ctx.fillText("GAME OVER", cx, cy - 30)

    ctx.font = "700 20px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    ctx.fillStyle = "#f8fafc"
    ctx.fillText(f"本局得分：{int(score)}   ·   历史最高：{int(best_score)}", cx, cy + 20)

    if last_is_new_record:
        ctx.font = "800 15px 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
        ctx.fillStyle = "#fde047"
        ctx.fillText("★ 刷新历史最高纪录 ★", cx, cy + 54)
    ctx.restore()


def _render():
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    if state == "playing" and not paused and shake > 0:
        amp = min(4.2, 1.0 + shake * 0.16)
        ctx.translate(randf(-amp, amp), randf(-amp, amp))

    draw_background()

    if state == "menu":
        return

    if boss is not None:
        boss.draw()

    for e in enemies:
        e.draw()

    for p in powers:
        p.draw()

    for b in bullets:
        b.draw()

    if player is not None:
        player.draw()
        _draw_clear_wave_aura()

    for fx in effects:
        fx.draw()

    for pt in particles:
        pt.draw()

    for ft in floating_texts:
        ft.draw()

    ctx.setTransform(1, 0, 0, 1, 0, 0)
    if boss is not None and state == "playing":
        boss.draw_overlay_ui()

    if state == "gameover":
        _draw_gameover_overlay()


def _main_loop(ts):
    global _raf_id, _last_ts, _accum_ms
    if _last_ts is None:
        _last_ts = ts
    dt = min(ts - _last_ts, 100.0)
    _last_ts = ts

    if state == "menu":
        step_background(0.45)
        _render()
    elif state == "playing":
        if not paused:
            _accum_ms += dt
            steps = 0
            while _accum_ms >= STEP_MS and steps < 3:
                _step_playing()
                _accum_ms -= STEP_MS
                steps += 1
                if state != "playing":
                    break
        _render()
    elif state == "gameover":
        step_background(0.25)
        for fx in list(effects):
            fx.update()
            if fx.t <= 0:
                safe_remove(effects, fx)
        for pt in list(particles):
            pt.update()
            if pt.life <= 0:
                safe_remove(particles, pt)
        _render()

    _raf_id = window.requestAnimationFrame(_raf_proxy)


def _sync_aria_visibility():
    is_playing = state == "playing"
    if hud_el is not None:
        hud_el.setAttribute("aria-hidden", "false" if is_playing else "true")
    if hud_controls_el is not None:
        hud_controls_el.setAttribute("aria-hidden", "false" if is_playing else "true")
    if pause_overlay_el is not None:
        pause_overlay_el.setAttribute("aria-hidden", "false" if (is_playing and paused) else "true")
    if menu_el is not None:
        menu_hidden = menu_el.style.display == "none"
        menu_el.setAttribute("aria-hidden", "true" if menu_hidden else "false")


def _show_menu_after_gameover():
    global _gameover_timer_id
    _gameover_timer_id = None
    if state == "gameover":
        menu_el.style.display = "flex"
        _sync_aria_visibility()


def end_game():
    global state, best_score, last_is_new_record, _gameover_timer_id
    state = "gameover"
    document.body.classList.remove("playing")
    document.body.classList.remove("paused")
    _sync_aria_visibility()
    _pause_bgm(reset_pos=True)
    reset_input()

    final_score = int(score)
    if final_score > best_score:
        best_score = final_score
        last_is_new_record = True
        _save_best_score(best_score)
    update_menu_records(last_run_score=final_score)

    if _gameover_timer_id is not None:
        window.clearTimeout(_gameover_timer_id)
    _gameover_timer_id = window.setTimeout(_show_menu_proxy, 1150)


def _sync_pause_button():
    if pause_btn is None:
        return
    glyph = pause_btn.querySelector(".icon-glyph")
    if glyph is not None:
        glyph.textContent = "▶" if paused else "⏸"


def toggle_pause(*_args):
    global paused, _last_ts, _accum_ms
    if state != "playing" or player is None or player.hp <= 0:
        return
    paused = not paused
    document.body.classList.toggle("paused", paused)
    _sync_pause_button()
    _sync_aria_visibility()
    if paused:
        reset_input()
        _pause_bgm(reset_pos=False)
    else:
        _last_ts = None
        _accum_ms = 0.0
        if not muted and _bgm_audio is not None:
            try:
                p = _bgm_audio.play()
                if p is not None and hasattr(p, "catch"):
                    p.catch(_noop_proxy)
            except Exception:
                pass
        canvas.focus()


def return_to_menu(*_args):
    global state, paused
    play_sound("button", 0.35)
    paused = False
    state = "menu"
    document.body.classList.remove("playing")
    document.body.classList.remove("paused")
    _sync_pause_button()
    _pause_bgm(reset_pos=True)
    reset_input()
    menu_el.style.display = "flex"
    _sync_aria_visibility()


def on_start(_evt=None):
    global state, selected_diff, _gameover_timer_id, _last_ts, _accum_ms
    if _gameover_timer_id is not None:
        window.clearTimeout(_gameover_timer_id)
        _gameover_timer_id = None

    play_sound("button", 0.38)
    menu_el.style.display = "none"
    canvas.focus()

    desired = getattr(window, "__desiredDifficulty", None)
    if desired in BASE_DIFF:
        selected_diff = str(desired)

    _start_bgm()
    document.body.classList.add("playing")
    reset_game()
    state = "playing"
    _sync_aria_visibility()
    _last_ts = None
    _accum_ms = 0.0


# ====== 输入控制（统一 Pointer Events + 键盘 WASD / 方向键 / 快捷键） ======
def _move_player_to_client(client_x, client_y):
    if state != "playing" or paused or player is None or player.hp <= 0:
        return
    rect = canvas.getBoundingClientRect()
    px = client_x - rect.left
    py = client_y - rect.top
    player.x = clamp(px - player.w / 2, 0, canvas.width - player.w)
    player.y = clamp(py - player.h / 2, 0, canvas.height - player.h)


def setup_controls():
    def on_keydown(e):
        code = getattr(e, "code", "")
        key = getattr(e, "key", "")
        if key in keys:
            e.preventDefault()
            keys[key] = True
            return
        if code in keys:
            e.preventDefault()
            keys[code] = True
            return
        if code in ("KeyP", "Escape") and not getattr(e, "repeat", False):
            toggle_pause()
        elif code == "KeyM" and not getattr(e, "repeat", False):
            toggle_mute()

    def on_keyup(e):
        code = getattr(e, "code", "")
        key = getattr(e, "key", "")
        if key in keys:
            keys[key] = False
        if code in keys:
            keys[code] = False

    def on_pointerdown(e):
        global pointer_active, active_pointer_id
        if state != "playing" or paused or player is None or player.hp <= 0:
            return
        pointer_active = True
        active_pointer_id = getattr(e, "pointerId", None)
        _move_player_to_client(e.clientX, e.clientY)
        try:
            canvas.setPointerCapture(active_pointer_id)
        except Exception:
            pass

    def on_pointermove(e):
        if not pointer_active:
            return
        pid = getattr(e, "pointerId", None)
        if active_pointer_id is not None and pid != active_pointer_id:
            return
        _move_player_to_client(e.clientX, e.clientY)

    def on_pointerup(e):
        global pointer_active, active_pointer_id
        pid = getattr(e, "pointerId", None)
        if active_pointer_id is not None and pid != active_pointer_id:
            return
        pointer_active = False
        active_pointer_id = None

    def on_blur(_e):
        reset_input()

    window.addEventListener("keydown", _keep_proxy(on_keydown))
    window.addEventListener("keyup", _keep_proxy(on_keyup))
    window.addEventListener("blur", _keep_proxy(on_blur))
    window.addEventListener("resize", _keep_proxy(lambda _e: fit_canvas()))

    canvas.addEventListener("pointerdown", _keep_proxy(on_pointerdown))
    canvas.addEventListener("pointermove", _keep_proxy(on_pointermove))
    canvas.addEventListener("pointerup", _keep_proxy(on_pointerup))
    canvas.addEventListener("pointercancel", _keep_proxy(on_pointerup))

    start_btn.addEventListener("click", _keep_proxy(on_start))
    if pause_btn is not None:
        pause_btn.addEventListener("click", _keep_proxy(toggle_pause))
    if mute_btn is not None:
        mute_btn.addEventListener("click", _keep_proxy(toggle_mute))
    if resume_btn is not None:
        resume_btn.addEventListener("click", _keep_proxy(toggle_pause))
    if menu_return_btn is not None:
        menu_return_btn.addEventListener("click", _keep_proxy(return_to_menu))


def _on_diff_changed(diff):
    global selected_diff
    if diff in BASE_DIFF:
        selected_diff = str(diff)
        play_sound("button", 0.22)


# ====== 启动初始化 ======
_raf_proxy = _keep_proxy(_main_loop)
_show_menu_proxy = _keep_proxy(_show_menu_after_gameover)
window.__onDiffChanged = _keep_proxy(_on_diff_changed)

desired_init = getattr(window, "__desiredDifficulty", None)
if desired_init in BASE_DIFF:
    selected_diff = str(desired_init)

fit_canvas()
setup_controls()
_sync_mute_button()
update_menu_records()

# 启动主渲染循环（首页态也维持深空星云与星尘动态流动）
_raf_id = window.requestAnimationFrame(_raf_proxy)

# 若用户在 Pyodide 初始化前已点击“开始游戏”，就绪后立即自动开局
if getattr(window, "__startClicked", False):
    window.__startClicked = False
    on_start(None)
