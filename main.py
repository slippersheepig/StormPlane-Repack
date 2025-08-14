import math
import random
import asyncio
from js import document, window

# ===== 游戏基础配置 =====
WIDTH = 480
HEIGHT = 800
FPS = 60

PLAYER_SPEED = 5
BULLET_SPEED = 10
ENEMY_SPEED = 3
BULLET_INTERVAL = 0.2  # 自动发射子弹间隔

# ===== 资源加载（使用 HTML5 Canvas 绘制） =====
canvas = document.getElementById("gameCanvas")
ctx = canvas.getContext("2d")

# 自适应屏幕
def resize_canvas():
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
resize_canvas()
window.addEventListener("resize", lambda e: resize_canvas())

# ===== 资源占位符（替换为 img/ 下的真实路径） =====
player_img = window.Image.new()
player_img.src = "img/player.png"

enemy_img = window.Image.new()
enemy_img.src = "img/enemy.png"

bullet_img = window.Image.new()
bullet_img.src = "img/bullet.png"

explosion_img = window.Image.new()
explosion_img.src = "img/explosion.png"

# ===== 游戏实体类 =====
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

    def collides_with(self, other):
        return not (
            self.x + self.width < other.x or
            self.x > other.x + other.width or
            self.y + self.height < other.y or
            self.y > other.y + other.height
        )

# ===== 玩家类 =====
class Player(Sprite):
    def __init__(self, img):
        super().__init__(img, WIDTH//2, HEIGHT - 100, 0)
        self.width = 60
        self.height = 60
        self.move_left = False
        self.move_right = False
        self.move_up = False
        self.move_down = False

player = Player(player_img)

# ===== 游戏状态 =====
bullets = []
enemies = []
score = 0
last_bullet_time = 0

# ===== 输入事件 =====
def on_key_down(e):
    key = e.key
    if key in ["ArrowLeft", "a"]:
        player.move_left = True
    elif key in ["ArrowRight", "d"]:
        player.move_right = True
    elif key in ["ArrowUp", "w"]:
        player.move_up = True
    elif key in ["ArrowDown", "s"]:
        player.move_down = True

def on_key_up(e):
    key = e.key
    if key in ["ArrowLeft", "a"]:
        player.move_left = False
    elif key in ["ArrowRight", "d"]:
        player.move_right = False
    elif key in ["ArrowUp", "w"]:
        player.move_up = False
    elif key in ["ArrowDown", "s"]:
        player.move_down = False

window.addEventListener("keydown", on_key_down)
window.addEventListener("keyup", on_key_up)

# ===== 自动发射子弹 =====
async def auto_fire():
    global last_bullet_time
    while True:
        bullet = Sprite(bullet_img, player.x + player.width//2 - 5, player.y - 10, -BULLET_SPEED)
        bullet.width = 10
        bullet.height = 20
        bullets.append(bullet)
        await asyncio.sleep(BULLET_INTERVAL)

# ===== 生成敌机 =====
async def spawn_enemies():
    while True:
        x = random.randint(0, canvas.width - 50)
        enemy = Sprite(enemy_img, x, -50, ENEMY_SPEED)
        enemies.append(enemy)
        await asyncio.sleep(1.0)

# ===== 游戏循环 =====
def update():
    # 玩家移动
    if player.move_left:
        player.x -= PLAYER_SPEED
    if player.move_right:
        player.x += PLAYER_SPEED
    if player.move_up:
        player.y -= PLAYER_SPEED
    if player.move_down:
        player.y += PLAYER_SPEED

    player.x = max(0, min(player.x, canvas.width - player.width))
    player.y = max(0, min(player.y, canvas.height - player.height))

    # 更新子弹
    for b in bullets:
        b.y += b.speed
    for b in list(bullets):
        if b.y < -20:
            bullets.remove(b)

    # 更新敌机
    for e in enemies:
        e.update()
    for e in list(enemies):
        if not e.alive:
            enemies.remove(e)

    # 碰撞检测
    global score
    for e in list(enemies):
        for b in list(bullets):
            if e.collides_with(b):
                enemies.remove(e)
                bullets.remove(b)
                score += 10
                break
        if e.collides_with(player):
            game_over()

def draw():
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    player.draw()
    for b in bullets:
        b.draw()
    for e in enemies:
        e.draw()
    ctx.fillStyle = "white"
    ctx.font = "20px Arial"
    ctx.fillText(f"得分: {score}", 10, 30)

def game_over():
    ctx.fillStyle = "red"
    ctx.font = "40px Arial"
    ctx.fillText("游戏结束", canvas.width/2 - 100, canvas.height/2)
    window.cancelAnimationFrame(animation_id)

def game_loop(timestamp):
    update()
    draw()
    global animation_id
    animation_id = window.requestAnimationFrame(game_loop)

# ===== 触屏事件 =====
touch_start_x = None
touch_start_y = None

def on_touch_start(e):
    global touch_start_x, touch_start_y
    touch = e.touches.item(0)
    touch_start_x = touch.clientX
    touch_start_y = touch.clientY
    e.preventDefault()

def on_touch_move(e):
    global touch_start_x, touch_start_y
    touch = e.touches.item(0)
    dx = touch.clientX - touch_start_x
    dy = touch.clientY - touch_start_y
    player.x += dx
    player.y += dy
    touch_start_x = touch.clientX
    touch_start_y = touch.clientY
    e.preventDefault()

canvas.addEventListener("touchstart", on_touch_start)
canvas.addEventListener("touchmove", on_touch_move)

# ===== 启动 =====
async def start_game():
    asyncio.create_task(auto_fire())
    asyncio.create_task(spawn_enemies())
    game_loop(0)

asyncio.ensure_future(start_game())
