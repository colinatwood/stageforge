#pragma once
#include <string>
#include <string_view>
namespace stageforge {
// Domain-separated SHA-256 of UTF-8 identity bytes; raw IDs never leave native probes.
std::string identity_hash(std::string_view domain, std::string_view utf8);
}
