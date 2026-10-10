/* One-shot Android arm64 clock snapshot. No files, threads, or wake locks. */
struct probe_timespec { long sec, nsec; };
extern int clock_gettime(int, struct probe_timespec *);
extern int printf(const char *, ...);
extern unsigned int getuid(void), geteuid(void);

int main(void) {
    struct probe_timespec monotonic, boottime, realtime;
    if (getuid() != 2000 || geteuid() != 2000) return 64;
    if (clock_gettime(1, &monotonic) || clock_gettime(7, &boottime)
            || clock_gettime(0, &realtime)) return 65;
    printf("{\"monotonic_ns\":%ld,\"boottime_ns\":%ld,\"unix_ns\":%ld}\n",
           monotonic.sec * 1000000000L + monotonic.nsec,
           boottime.sec * 1000000000L + boottime.nsec,
           realtime.sec * 1000000000L + realtime.nsec);
    return 0;
}
