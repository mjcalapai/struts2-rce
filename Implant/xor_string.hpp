// xor_string.hpp
#pragma once
#include <string>
#include <array>

namespace detail {
    template<size_t N>
    struct XorString {
        constexpr XorString(const char (&str)[N]) : data{} {
            for (size_t i = 0; i < N; ++i)
                data[i] = str[i] ^ 0x55;
        }
        std::array<char, N> data;
        std::string decrypt() const {
            std::string out;
            out.reserve(N - 1);  // exclude null terminator
            for (size_t i = 0; i < N - 1; ++i)
                out.push_back(data[i] ^ 0x55);
            return out;
        }
    };
}

#define XOR_STR(s) (detail::XorString(s).decrypt())