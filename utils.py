import random

def rects_collide(a, b):
    """
    矩形碰撞检测
    a, b: 对象需有 x, y, width, height 属性
    """
    return not (
        a.x + a.width < b.x or
        a.x > b.x + b.width or
        a.y + a.height < b.y or
        a.y > b.y + b.height
    )

def random_position(canvas_width, sprite_width):
    """
    在画布宽度范围内随机生成 X 坐标
    """
    return random.randint(0, canvas_width - sprite_width)

def clamp(value, min_value, max_value):
    """
    限制数值范围
    """
    return max(min_value, min(value, max_value))
