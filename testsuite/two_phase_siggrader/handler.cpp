#include <iostream>

#include "header.h"

int main() {
#ifdef SIGNATURE_PHASE_1
    int a, b;
    std::cin >> a >> b;
    std::cout << first_phase(a, b) << '\n';
    return 0;
#endif

#ifdef SIGNATURE_PHASE_2
    int a, b, mid;
    std::cin >> a >> b >> mid;
    std::cout << second_phase(a, b, mid) << '\n';
    return 0;
#endif
}
