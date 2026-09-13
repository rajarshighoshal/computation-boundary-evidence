function advance(initial, flow, dt) {
  const loss = flow * dt;
  const updated = initial - loss;
  if (updated < 0) throw new Error("negative inventory");
  return updated;
}
