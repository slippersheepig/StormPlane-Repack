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
    """限制 value 在 [min_value, max_value] 范围内"""
    return max(min_value, min(value, max_value))
