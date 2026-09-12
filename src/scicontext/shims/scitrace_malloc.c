#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>

/* Observe-only allocation counter. Loaded via LD_PRELOAD into a traced
   process tree; counts malloc/calloc calls and bytes for processes whose
   executable basename matches $SCITRACE_EXE (or, unset, any non-python
   executable). free/realloc sizes are untracked and reported as such. */

static __thread long tl_calls = 0, tl_bytes = 0, tl_peak = 0, tl_live = 0;
static void *(*real_malloc)(size_t);
static void *(*real_calloc)(size_t, size_t);
static void *(*real_realloc)(void *, size_t);
static void (*real_free)(void *);
static int gated = -1;

static int count_this(void) {
    if (gated >= 0) return gated;
    const char *target = getenv("SCITRACE_EXE");
    char self[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
    if (n <= 0) { gated = 0; return 0; }
    self[n] = 0;
    const char *base = strrchr(self, '/');
    base = base ? base + 1 : self;
    if (target && *target) {
        gated = strcmp(base, target) == 0;
    } else {
        gated = strncmp(base, "python", 6) != 0;
    }
    return gated;
}

__attribute__((constructor)) static void init(void) {
    real_malloc = dlsym(RTLD_NEXT, "malloc");
    real_calloc = dlsym(RTLD_NEXT, "calloc");
    real_realloc = dlsym(RTLD_NEXT, "realloc");
    real_free = dlsym(RTLD_NEXT, "free");
}

static void account(long requested) {
    if (!count_this() || requested <= 0) return;
    tl_calls++;
    tl_bytes += requested;
    tl_live += requested;
    if (tl_live > tl_peak) tl_peak = tl_live;
}

void *malloc(size_t size) {
    void *p = real_malloc(size);
    if (p) account((long)size);
    return p;
}
void *calloc(size_t n, size_t size) {
    void *p = real_calloc(n, size);
    if (p) account((long)(n * size));
    return p;
}
void *realloc(void *p, size_t size) {
    void *q = real_realloc(p, size);
    if (q) account((long)size);
    return q;
}
void free(void *p) { real_free(p); }

__attribute__((destructor)) static void finish(void) {
    if (!count_this()) return;
    const char *out = getenv("SCITRACE_OUT");
    if (!out || !*out) return;
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/malloc.%d.json", out, (int)getpid());
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "{\"calls\": %ld, \"bytes_requested\": %ld, \"peak_live_estimate\": %ld, \"live_at_exit\": %ld, \"note\": \"malloc/calloc sizes only; free/realloc sizes untracked\"}\n",
            tl_calls, tl_bytes, tl_peak, tl_live);
    fclose(f);
}
