from js import document, window
import math
import random
from utils import rects_collide, clamp

# ===== Canvas =====
canvas = document.getElementById("game-canvas")
ctx = canvas.getContext("2d")

def resize_canvas():
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight

resize_canvas()
window.addEventListener("resize", lambda e: resize_canvas())

# ===== 使用原仓库文件名（保持后缀一致） =====
IMAGES = {
    "player": "red_plane.png",             # 玩家飞机（/img/red_plane.png）
    "bullet": "red_bullet.png",            # 我方子弹（/img/red_bullet.png）
    "enemy_small": "small_enemy.png",      # 小型敌机（/img/small_enemy.png）
    "enemy_middle": "middle_enemy.png",    # 中型敌机（/img/middle_enemy.png）
    "enemy_big": "big_enemy.png",          # 大型敌机（/img/big_enemy.png）
    "explosion": "boom.png",               # 爆炸效果（/img/boom.png，来自 res/drawable-mdpi/boom.png）
    "bg1": "bg_01.jpg",                    # 背景1（/img/bg_01.jpg，来自 res/drawable-mdpi/bg_01.jpg）
    "bg2": "bg_02.jpg",                    # 背景2（/img/bg_02.jpg，来自 res/drawable-mdpi/bg_02.jpg）
}

SOUNDS = {
    "shoot": "shoot.mp3",                  # 射击音效（/sound/shoot.mp3）
    "explosion_small": "explosion2.wav",   # 小型爆炸（/sound/explosion2.wav）
    "explosion_big": "bigexplosion.wav",   # 大型爆炸（/sound/bigexplosion.wav）
    "gameover": "explosion3.wav",          # 游戏结束（/sound/explosion3.wav）
    "get_goods": "get_goods.wav",          # 获得道具（/sound/get_goods.wav）
    "bgm": "game.mp3",                     # 背景音乐（/sound/game.mp3）
}

# ===== 资源加载 =====
def load_image(filename):
    img = window.Image.new()
    img.src = f"img/{filename}"
    return img

def load_sound(filename, loop=False, volume=1.0):
    audio = window.Audio.new(f"sound/{filename}")
    audio.loop = loop
    audio.volume = volume
    return audio

# 载入图片
images = {k: load_image(v) for k, v in IMAGES.items()}

# 载入音效
sounds = {
    "shoot": load_sound(SOUNDS["shoot"], loop=False, volume=0.45),
    "explosion_small": load_sound(SOUNDS["explosion_small"], loop=False, volume=0.6),
    "explosion_big": load_sound(SOUNDS["explosion_big"], loop=False, volume=0.6),
    "gameover": load_sound(SOUNDS["gameover"], loop=False, volume=0.7),
    "get_goods": load_sound(SOUNDS["get_goods"], loop=False, volume=0.5),
    "bgm": load_sound(SOUNDS["bgm"], loop=True, volume=0.35),
}

# 背景自动播放需要一次用户交互解锁音频策略（移动端）
_audio_unlocked = {"value": False}
def _unlock_audio(_evt=None):
    if not _audio_unlocked["value"]:
        try:
            sounds["bgm"].play()
        except Exception as _e:
            pass
        _audio_unlocked["value"] = True
        document.removeEventListener("touchstart", _unlock_audio)
        document.removeEventListener("mousedown", _unlock_audio)
        document.removeEventListener("keydown", _unlock_audio)

document.addEventListener("touchstart", _unlock_audio)
document.addEventListener("mousedown", _unlock_audio)
document.addEventListener("keydown", _unlock_audio)

# ===== 背景滚动 =====
bg_scroll_y = 0
def draw_background():
    global bg_scroll_y
    h = canvas.height
    w = canvas.width
    speed = 1.5

    bg1 = images["bg1"]
    bg2 = images["bg2"]
    # 拉伸铺满
    ctx.drawImage(bg1, 0, bg_scroll_y - h, w, h)
    ctx.drawImage(bg2, 0, bg_scroll_y, w, h)
    bg_scroll_y += speed
    if bg_scroll_y >= h:
        bg_scroll_y = 0

# ===== 基础类 =====
class Sprite:
    def __init__(self, img, x, y, w, h, vx=0, vy=0):
        self.img = img
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.vx = vx
        self.vy = vy
        self.alive = True

    def draw(self):
        ctx.drawImage(self.img, self.x, self.y, self.w, self.h)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y > canvas.height + 100 or self.y < -200 or self.x < -200 or self.x > canvas.width + 200:
            self.alive = False

class Player(Sprite):
    def __init__(self):
        size = max(48, min(canvas.width, canvas.height) * 0.08)
        super().__init__(images["player"], canvas.width/2 - size/2, canvas.height - size*1.5, size, size)
        self.cooldown = 0
        self.speed = max(4, size * 0.12)

    def shoot(self):
        if self.cooldown <= 0:
            b_w = max(10, self.w * 0.18)
            b_h = b_w * 1.8
            bx = self.x + self.w/2 - b_w/2
            by = self.y - b_h + 4
            bullets.append(Sprite(images["bullet"], bx, by, b_w, b_h, vy=-9))
            try:
                sounds["shoot"].currentTime = 0
                sounds["shoot"].play()
            except Exception:
                pass
            self.cooldown = 10  # 自动射击间隔帧

    def handle_input(self):
        dx = (keys["ArrowRight"] - keys["ArrowLeft"]) * self.speed
        dy = (keys["ArrowDown"] - keys["ArrowUp"]) * self.speed
        self.x += dx
        self.y += dy
        self.x = clamp(self.x, 0, canvas.width - self.w)
        self.y = clamp(self.y, 0, canvas.height - self.h)

    def update(self):
        if self.cooldown > 0:
            self.cooldown -= 1
        self.shoot()
        self.draw()

class Enemy(Sprite):
    def __init__(self, kind, x, y, speed):
        if kind == "small":
            img = images["enemy_small"]
            base = 42
            score = 5
            hp = 1
        elif kind == "middle":
            img = images["enemy_middle"]
            base = 64
            score = 10
            hp = 3
        else:
            img = images["enemy_big"]
            base = 92
            score = 30
            hp = 8
        size = max(base, min(canvas.width, canvas.height) * (base/480))
        super().__init__(img, x, y, size, size, vy=speed)
        self.kind = kind
        self.hp = hp
        self.score = score

# ===== 游戏集合 =====
player = Player()
bullets = []
enemies = []
score = 0
game_over = False
spawn_timer = 0

# ===== 键鼠与触摸 =====
keys = {"ArrowLeft":0, "ArrowRight":0, "ArrowUp":0, "ArrowDown":0}

def on_key_down(e):
    if e.key in keys:
        keys[e.key] = 1
def on_key_up(e):
    if e.key in keys:
        keys[e.key] = 0

document.addEventListener("keydown", on_key_down)
document.addEventListener("keyup", on_key_up)

# 触摸拖动
_touch = {"x": None, "y": None}
def on_touch_start(e):
    t = e.touches[0]
    _touch["x"] = t.clientX
    _touch["y"] = t.clientY
def on_touch_move(e):
    t = e.touches[0]
    dx = t.clientX - _touch["x"]
    dy = t.clientY - _touch["y"]
    player.x += dx
    player.y += dy
    player.x = clamp(player.x, 0, canvas.width - player.w)
    player.y = clamp(player.y, 0, canvas.height - player.h)
    _touch["x"] = t.clientX
    _touch["y"] = t.clientY
def on_touch_end(e):
    _touch["x"] = None
    _touch["y"] = None

canvas.addEventListener("touchstart", on_touch_start)
canvas.addEventListener("touchmove", on_touch_move)
canvas.addEventListener("touchend", on_touch_end)

# ===== 生成敌机 =====
def spawn_enemy():
    global spawn_timer
    spawn_timer += 1
    if spawn_timer < 15:
        return
    spawn_timer = 0
    r = random.random()
    if r < 0.65:
        kind = "small"
        speed = random.uniform(2.5, 4.5)
    elif r < 0.9:
        kind = "middle"
        speed = random.uniform(2.0, 3.2)
    else:
        kind = "big"
        speed = random.uniform(1.4, 2.1)

    size_hint = 60 if kind=="small" else (84 if kind=="middle" else 120)
    x = random.uniform(0, canvas.width - size_hint)
    enemies.append(Enemy(kind, x, -size_hint, speed))

# ===== 碰撞 & 结算 =====
def handle_collisions():
    global score, game_over
    # 子弹命中敌机
    for b in bullets[:]:
        for e in enemies[:]:
            if rects_collide(b, e):
                bullets.remove(b)
                e.hp -= 1
                if e.hp <= 0:
                    enemies.remove(e)
                    score += e.score
                    try:
                        if e.kind == "big":
                            sounds["explosion_big"].currentTime = 0
                            sounds["explosion_big"].play()
                        else:
                            sounds["explosion_small"].currentTime = 0
                            sounds["explosion_small"].play()
                    except Exception:
                        pass
                break
    # 敌机撞玩家
    for e in enemies[:]:
        if rects_collide(e, player):
            game_over = True
            try:
                sounds["gameover"].play()
            except Exception:
                pass
            break

# ===== 主循环 =====
def update():
    global game_over
    # 背景
    draw_background()

    # 玩家
    player.handle_input()
    player.update()

    # 子弹
    for b in bullets[:]:
        b.update()
        b.draw()
        if not b.alive:
            bullets.remove(b)

    # 敌机
    for e in enemies[:]:
        e.update()
        e.draw()
        if not e.alive:
            enemies.remove(e)

    # 逻辑
    handle_collisions()
    spawn_enemy()

    # HUD
    ctx.fillStyle = "white"
    ctx.font = "20px Arial"
    ctx.fillText(f"Score: {score}", 12, 28)

    if not game_over:
        window.requestAnimationFrame(lambda *_: update())
    else:
        ctx.fillStyle = "rgba(0,0,0,0.45)"
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.fillStyle = "red"
        ctx.font = "42px Arial"
        ctx.fillText("GAME OVER", canvas.width/2 - 120, canvas.height/2)

# 启动
update()
