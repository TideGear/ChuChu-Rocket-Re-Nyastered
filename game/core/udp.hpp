// Minimal non-blocking UDP socket (Winsock on Windows, BSD sockets elsewhere incl. Android). IPv4. Carries the byte packets of Lockstep.
#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET sock_t;
#define CCR_INVALID_SOCK INVALID_SOCKET
static inline void ccrCloseSock(sock_t s) { closesocket(s); }
#else
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int sock_t;
#define CCR_INVALID_SOCK (-1)
static inline void ccrCloseSock(sock_t s) { close(s); }
#endif
namespace ccr {
struct UdpAddr { uint32_t ip = 0; uint16_t port = 0; };       // host byte order
class UdpSocket {
public:
    sock_t s = CCR_INVALID_SOCK;
    ~UdpSocket() { close(); }
    // bind to the given local ip (e.g. "127.0.0.1" for tests, "0.0.0.0" for LAN/online) and port (0 = any); returns the port actually bound or 0 on failure
    uint16_t open(const char* ip, uint16_t port) {
#ifdef _WIN32
        static bool wsa = false; if (!wsa) { WSADATA d; WSAStartup(MAKEWORD(2, 2), &d); wsa = true; }
#endif
        s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP); if (s == CCR_INVALID_SOCK) return 0;
#ifdef _WIN32
        u_long nb = 1; ioctlsocket(s, FIONBIO, &nb);
#else
        fcntl(s, F_SETFL, fcntl(s, F_GETFL, 0) | O_NONBLOCK);
#endif
        sockaddr_in a{}; a.sin_family = AF_INET; a.sin_port = htons(port); inet_pton(AF_INET, ip, &a.sin_addr);
        if (bind(s, (sockaddr*)&a, sizeof a) != 0) { close(); return 0; }
        socklen_t l = sizeof a; getsockname(s, (sockaddr*)&a, &l); return ntohs(a.sin_port);
    }
    void close() { if (s != CCR_INVALID_SOCK) { ccrCloseSock(s); s = CCR_INVALID_SOCK; } }
    bool send(const UdpAddr& to, const std::vector<uint8_t>& d) {
        sockaddr_in a{}; a.sin_family = AF_INET; a.sin_port = htons(to.port); a.sin_addr.s_addr = htonl(to.ip);
        return sendto(s, (const char*)d.data(), (int)d.size(), 0, (sockaddr*)&a, sizeof a) == (int)d.size();
    }
    bool recv(std::vector<uint8_t>& out, UdpAddr* from = nullptr) {
        uint8_t buf[2048]; sockaddr_in a{}; socklen_t l = sizeof a;
        int n = recvfrom(s, (char*)buf, sizeof buf, 0, (sockaddr*)&a, &l); if (n <= 0) return false;
        out.assign(buf, buf + n); if (from) { from->ip = ntohl(a.sin_addr.s_addr); from->port = ntohs(a.sin_port); } return true;
    }
};
inline UdpAddr makeAddr(const char* ip, uint16_t port) { in_addr a{}; inet_pton(AF_INET, ip, &a); UdpAddr r; r.ip = ntohl(a.s_addr); r.port = port; return r; }
} // namespace ccr
