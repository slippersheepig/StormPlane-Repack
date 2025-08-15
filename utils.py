def rects_collide(a, b):
    # 兼容使用 w/h 或 rect.width/height 的对象
    aw = getattr(a, 'w', getattr(a, 'width', 0))
    ah = getattr(a, 'h', getattr(a, 'height', 0))
    bw = getattr(b, 'w', getattr(b, 'width', 0))
    bh = getattr(b, 'h', getattr(b, 'height', 0))

    return not (
        a.x + aw < b.x or
        a.x > b.x + bw or
        a.y + ah < b.y or
        a.y > b.y + bh
    )

def clamp(value, min_value, max_value):
    # 限制 value 在 [min_value, max_value] 范围内
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value

import random
from js import Image

def randf(a, b):
    return random.random()*(b-a)+a

def load_sprite(path):
    # 尝试加载图片，失败则返回 None
    try:
        img = Image.new()
        img.src = path
        return img
    except Exception:
        return None
