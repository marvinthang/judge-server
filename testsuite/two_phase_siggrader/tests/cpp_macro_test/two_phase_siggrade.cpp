#include "header.h"

int first_phase(int a, int b) {
#ifdef SIGNATURE_PHASE_1
    return a + b;
#else
    return -1000;
#endif
}

int second_phase(int a, int b, int mid) {
#ifdef SIGNATURE_PHASE_2
    return mid * 2;
#else
    return a + b;
#endif
}
