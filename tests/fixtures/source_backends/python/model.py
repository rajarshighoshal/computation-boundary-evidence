raise RuntimeError("Analysis must not execute candidate code")

def scale(value, factor):
    return value * factor

def advance(initial, flow, dt):
    loss = scale(flow, dt)
    updated = initial - loss
    if updated < 0:
        raise ValueError("negative inventory")
    return updated
