module inventory
contains
function scale(value, factor) result(output)
real, intent(in) :: value, factor
real :: output
output = value * factor
end function
function advance(initial, flow, dt) result(updated)
real, intent(in) :: initial, flow, dt
real :: updated
updated = initial - scale(flow, dt)
end function
end module
