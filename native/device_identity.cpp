#include "device_identity.h"
#include <array>
#include <limits>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#else
#include <CommonCrypto/CommonDigest.h>
#endif

namespace stageforge {
std::string identity_hash(std::string_view domain, std::string_view utf8) {
    if (domain.empty() || utf8.empty() || domain.find('\0') != std::string_view::npos)
        throw std::invalid_argument("identity domain and value must be nonempty");
    std::string input(domain);
    input.push_back('\0');
    input.append(utf8);
    if (input.size() > std::numeric_limits<unsigned>::max())
        throw std::length_error("identity too long");
    std::array<unsigned char,32> digest{};
#ifdef _WIN32
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0)
        throw std::runtime_error("open SHA256 provider failed");
    auto status = BCryptHash(algorithm, nullptr, 0,
        reinterpret_cast<PUCHAR>(input.data()), static_cast<ULONG>(input.size()),
        digest.data(), static_cast<ULONG>(digest.size()));
    BCryptCloseAlgorithmProvider(algorithm, 0);
    if (status < 0) throw std::runtime_error("SHA256 failed");
#else
    if (!CC_SHA256(input.data(), static_cast<CC_LONG>(input.size()), digest.data()))
        throw std::runtime_error("SHA256 failed");
#endif
    constexpr char hex[] = "0123456789abcdef";
    std::string result = "sha256:";
    for (auto byte : digest) { result += hex[byte >> 4]; result += hex[byte & 15]; }
    return result;
}
}
