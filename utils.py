import random


def rects_collide(a, b):
    """检测两个矩形实体是否发生轴对齐包围盒碰撞。"""
    aw = getattr(a, "w", getattr(a, "width", 0))
    ah = getattr(a, "h", getattr(a, "height", 0))
    bw = getattr(b, "w", getattr(b, "width", 0))
    bh = getattr(b, "h", getattr(b, "height", 0))

    return not (
        a.x + aw < b.x
        or a.x > b.x + bw
        or a.y + ah < b.y
        or a.y > b.y + bh
    )


def clamp(value, min_value, max_value):
    """将数值限制在 [min_value, max_value] 区间内。"""
    if max_value < min_value:
        return min_value
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def randf(a, b):
    """返回 [a, b] 范围内的随机浮点数。"""
    return random.uniform(a, b)
