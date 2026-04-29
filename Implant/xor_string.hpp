// xor_string.hpp
#pragma once
#include <string>
#include <array>
#include <algorithm>
#include <cstring>

// Define a default key (0x5A), gets overridden at compile time
#ifndef XOR_KEY
#define XOR_KEY 0x5A
#endif

namespace detail {
    template<size_t N>
    struct XorString {
        constexpr XorString(const char (&str)[N]) : data{} {
            for (size_t i = 0; i < N; ++i)
                data[i] = str[i] ^ XOR_KEY;
        }
        std::array<char, N> data;
        
        // Normal decrypt
        std::string decrypt() const {
            std::string out;
            out.reserve(N - 1);
            for (size_t i = 0; i < N - 1; ++i)
                out.push_back(data[i] ^ XOR_KEY);
            return out;
        }

        // Secure decrypt
        class SecureString {
            char* ptr;
            size_t len;
        public:
            SecureString(const XorString& xs) : len(xs.N - 1) {
                ptr = new char[len + 1];
                for (size_t i = 0; i < len; ++i)
                    ptr[i] = xs.data[i] ^ XOR_KEY;
                ptr[len] = 0;
            }
            ~SecureString() {
                if (ptr) {
                    volatile char* p = ptr;
                    for (size_t i = 0; i < len; ++i) p[i] = 0;
                    delete[] ptr;
                }
            }
            SecureString(SecureString&& other) noexcept : ptr(other.ptr), len(other.len) {
                other.ptr = nullptr;
                other.len = 0;
            }
            SecureString& operator=(SecureString&& other) noexcept {
                if (this != &other) {
                    delete[] ptr;
                    ptr = other.ptr;
                    len = other.len;
                    other.ptr = nullptr;
                }
                return *this;
            }
            //Disable copy
            SecureString(const SecureString&) = delete;
            SecureString& operator=(const SecureString&) = delete;
            
            const char* c_str() const { return ptr; }
            size_t size() const { return len; }
            operator std::string() const { return std::string(ptr, len); }
        };
        
        SecureString secure_decrypt() const {
            return SecureString(*this);
        }
    };
}

// Macro returns a temporary XorString then calls decrypt()
#define XOR_STR(s) (detail::XorString(s).decrypt())
// Secure version (auto‑wiping)
#define XOR_STR_SECURE(s) (detail::XorString(s).secure_decrypt())