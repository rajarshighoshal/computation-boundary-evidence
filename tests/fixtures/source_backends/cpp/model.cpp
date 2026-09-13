double scale(double value, double factor) { return value * factor; }
double advance(double initial, double flow, double dt) {
    double loss = scale(flow, dt);
    double updated = initial - loss;
    if (updated < 0) return 0;
    return updated;
}
