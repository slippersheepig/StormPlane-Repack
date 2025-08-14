def rects_collide(a, b):
    """检测两个矩形是否碰撞"""
    return not (
        a.x + a.width < b.x or
        a.x > b.x + b.width or
        a.y + a.height < b.y or
        a.y > b.y + b.height
    )

def clamp(value, min_value, max_value):
    """限制 value 在 [min_value, max_value] 范围内"""
    return max(min_value, min(value, max_value))
