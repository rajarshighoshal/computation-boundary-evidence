def storage_step(previous_volume, outward_flow, duration):
    """Update stored water volume using a positive-outward flow convention."""
    return previous_volume + outward_flow * duration
