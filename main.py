from js import document, window
import math
import random
from utils import rects_collide, clamp

# ===== 获取 Canvas 和上下文 =====
canvas = document.getElementById("game-canvas")
ctx = canvas.getContext("2d")

# 根据屏幕尺寸设置画布大小
canvas.width = window.innerWidth
canvas.height = window.innerHeight

# ===== 资源加载 =====
def load_image(name):
    img = window.Image.new()
    img.src = f"img/{name}"
    return img

def load_sound(name):
    audio = window.Audio.new(f"sound/{name}")
    return audio

# 图片资源
player_img = load_image("player.png")
player_hit_img = load_image("player_hit.png")
enemy_img = load_image("enemy.png")
enemy_hit_img = load_image("enemy_hit.png")
bullet_img = load_image("bullet.png")
explosion_img = load_image("explosion.png")

# 音效
shoot_sound = load_sound("shoot.wav")
explosion_sound = load_sound("explosion.wav")
hit_sound = load_sound("hit.wav")
gameover_sound = load_sound("gameover.wav")

# ===== 类定义 =====
class Sprite:
    def __init__(self, img, x, y, speed=0):
        self.img = img
        self.x = x
        self.y = y
        self.speed = speed
        self.width = 50
        self.height = 50
        self.alive = True

    def draw(self):
        ctx.drawImage(self.img, self.x, self.y, self.width, self.height)

    def update(self):
        self.y += self.speed
        if self.y > canvas.height:
            self.alive = False

class Player(Sprite):
    def __init__(self):
        super().__init__(player_img, canvas.width//2 - 25, canvas.height - 80, 0)
        self.width = 60
        self.height = 60
        self.cooldown = 0

    def shoot(self):
        if self.cooldown == 0:
            bullet = Bullet(bullet_img, self.x + self.width//2 - 5, self.y - 10, -8)
            bullets.append(bullet)
            shoot_sound.play()
            self.cooldown = 15  # 自动射击间隔

    def update(self):
        if self.cooldown > 0:
            self.cooldown -= 1
        self.shoot()
        self.draw()

class Enemy(Sprite):
    def __init__(self, x, y, speed):
        super().__init__(enemy_img, x, y, speed)

class Bullet(Sprite):
    def __init__(self, img, x, y, speed):
        super().__init__(img, x, y, speed)
        self.width = 10
        self.height = 20

# ===== 游戏对象容器 =====
player = Player()
enemies = []
bullets = []

score = 0
game_over = False

# ===== 键盘控制 =====
keys = {"ArrowLeft": False, "ArrowRight": False, "ArrowUp": False, "ArrowDown": False}

def on_key_down(e):
    if e.key in keys:
        keys[e.key] = True

def on_key_up(e):
    if e.key in keys:
        keys[e.key] = False

document.addEventListener("keydown", on_key_down)
document.addEventListener("keyup", on_key_up)

# ===== 触屏控制 =====
touch_x = None
touch_y = None

def on_touch_start(e):
    global touch_x, touch_y
    touch = e.touches[0]
    touch_x = touch.clientX
    touch_y = touch.clientY

def on_touch_move(e):
    global touch_x, touch_y
    touch = e.touches[0]
    dx = touch.clientX - touch_x
    dy = touch.clientY - touch_y
    player.x += dx
    player.y += dy
    touch_x = touch.clientX
    touch_y = touch.clientY

def on_touch_end(e):
    pass

canvas.addEventListener("touchstart", on_touch_start)
canvas.addEventListener("touchmove", on_touch_move)
canvas.addEventListener("touchend", on_touch_end)

# ===== 游戏逻辑 =====
def spawn_enemy():
    x = random.randint(0, canvas.width - 50)
    y = -50
    speed = random.randint(2, 5)
    enemies.append(Enemy(x, y, speed))

def update():
    global score, game_over

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    # 玩家移动
    if keys["ArrowLeft"]:
        player.x -= 5
    if keys["ArrowRight"]:
        player.x += 5
    if keys["ArrowUp"]:
        player.y -= 5
    if keys["ArrowDown"]:
        player.y += 5

    player.x = clamp(player.x, 0, canvas.width - player.width)
    player.y = clamp(player.y, 0, canvas.height - player.height)

    # 绘制玩家
    player.update()

    # 绘制和更新子弹
    for bullet in bullets[:]:
        bullet.update()
        bullet.draw()
        if not bullet.alive:
            bullets.remove(bullet)

    # 绘制和更新敌机
    for enemy in enemies[:]:
        enemy.update()
        enemy.draw()
        if not enemy.alive:
            enemies.remove(enemy)

    # 碰撞检测
    for enemy in enemies[:]:
        # 子弹命中敌机
        for bullet in bullets[:]:
            if rects_collide(bullet, enemy):
                explosion_sound.play()
                enemies.remove(enemy)
                bullets.remove(bullet)
                score += 10
                break
        # 敌机撞到玩家
        if rects_collide(enemy, player):
            gameover_sound.play()
            game_over = True
            break

    # 分数
    ctx.fillStyle = "white"
    ctx.font = "20px Arial"
    ctx.fillText(f"Score: {score}", 10, 30)

    if game_over:
        ctx.fillStyle = "red"
        ctx.font = "40px Arial"
        ctx.fillText("GAME OVER", canvas.width/2 - 100, canvas.height/2)
    else:
        if random.random() < 0.02:
            spawn_enemy()
        window.requestAnimationFrame(update)

# 启动游戏
update()
