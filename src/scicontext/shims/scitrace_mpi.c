#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>

/* Observe-only MPI interceptor. Wraps MPI_Init/Init_thread/Finalize and the
   point-to-point/collective calls with void* handle passthrough (compatible
   with both OpenMPI pointer handles and MPICH integer handles since we never
   interpret them), logging (rank, count, tag, comm) to $SCITRACE_OUT.
   Conditional build: only when the traced executable links libmpi. */

#define WRAP(name) \
    static void *(*real_##name)(void); \
    void name(void *a) { \
        void *r = ((void *(*)(void))real_##name)(a); \
        log_call(#name); \
        return r; \
    }

static FILE *log_file = NULL;
static int rank_cache = -1;

static void ensure_log(void) {
    if (log_file) return;
    const char *out = getenv("SCITRACE_OUT");
    if (!out || !*out) return;
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/mpi.%d.jsonl", out, (int)getpid());
    log_file = fopen(path, "a");
}

static void log_call(const char *name) {
    ensure_log();
    if (!log_file) return;
    fprintf(log_file, "{\"call\": \"%s\", \"rank\": %d}\n", name, rank_cache);
    fflush(log_file);
}

__attribute__((constructor)) static void init(void) { (void)0; }

void MPI_Init(void *a, void *b) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Init");
    int r = ((int (*)(void *, void *))real)(a, b);
    if (r == 0) {
        static int (*rank_fn)(void *, int *) = NULL;
        if (!rank_fn) rank_fn = dlsym(RTLD_NEXT, "MPI_Comm_rank");
        int rank = -1;
        if (rank_fn && rank_fn(a, &rank) == 0) rank_cache = rank;
    }
    log_call("MPI_Init");
}

void MPI_Init_thread(void *a, void *b, void *c, void *d) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Init_thread");
    int r = ((int (*)(void *, void *, void *, void *))real)(a, b, c, d);
    if (r == 0) {
        static int (*rank_fn)(void *, int *) = NULL;
        if (!rank_fn) rank_fn = dlsym(RTLD_NEXT, "MPI_Comm_rank");
        int rank = -1;
        if (rank_fn && rank_fn(a, &rank) == 0) rank_cache = rank;
    }
    log_call("MPI_Init_thread");
}

void MPI_Finalize(void *a) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Finalize");
    log_call("MPI_Finalize");
    int r = ((int (*)(void *))real)(a);
    (void)r;
    if (log_file) { fclose(log_file); log_file = NULL; }
}

void MPI_Send(void *a, void *b, void *c, void *d, void *e, void *f, void *g) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Send");
    int r = ((int (*)(void *, void *, void *, void *, void *, void *, void *))real)(a, b, c, d, e, f, g);
    if (r == 0) {
        ensure_log();
        if (log_file) {
            fprintf(log_file, "{\"call\": \"MPI_Send\", \"rank\": %d, \"count\": %ld, \"dest\": %ld, \"tag\": %ld}\n",
                    rank_cache, (long)c, (long)e, (long)f);
            fflush(log_file);
        }
    }
}

void MPI_Recv(void *a, void *b, void *c, void *d, void *e, void *f, void *g, void *h) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Recv");
    int r = ((int (*)(void *, void *, void *, void *, void *, void *, void *, void *))real)(a, b, c, d, e, f, g, h);
    if (r == 0) {
        ensure_log();
        if (log_file) {
            fprintf(log_file, "{\"call\": \"MPI_Recv\", \"rank\": %d, \"count\": %ld, \"source\": %ld, \"tag\": %ld}\n",
                    rank_cache, (long)c, (long)e, (long)f);
            fflush(log_file);
        }
    }
}

void MPI_Barrier(void *a) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Barrier");
    int r = ((int (*)(void *))real)(a);
    if (r == 0) log_call("MPI_Barrier");
}

void MPI_Bcast(void *a, void *b, void *c, void *d, void *e) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Bcast");
    int r = ((int (*)(void *, void *, void *, void *, void *))real)(a, b, c, d, e);
    if (r == 0) log_call("MPI_Bcast");
}

void MPI_Reduce(void *a, void *b, void *c, void *d, void *e, void *f, void *g, void *h) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Reduce");
    int r = ((int (*)(void *, void *, void *, void *, void *, void *, void *, void *))real)(a, b, c, d, e, f, g, h);
    if (r == 0) log_call("MPI_Reduce");
}

void MPI_Allreduce(void *a, void *b, void *c, void *d, void *e, void *f) {
    static void *(*real)(void) = NULL;
    if (!real) real = dlsym(RTLD_NEXT, "MPI_Allreduce");
    int r = ((int (*)(void *, void *, void *, void *, void *, void *))real)(a, b, c, d, e, f);
    if (r == 0) log_call("MPI_Allreduce");
}
