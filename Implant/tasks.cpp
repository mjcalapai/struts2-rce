#include "tasks.h"

#include <string>
#include <array>
#include <sstream>
#include <fstream>
#include <cstdlib>
#include <functional>
#include <stdexcept>

#include <boost/uuid/uuid_io.hpp>
#include <boost/property_tree/ptree.hpp>

// Only include Windows APIs on Windows
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <tlhelp32.h>
#endif

[[nodiscard]] Task parseTaskFrom(
    const boost::property_tree::ptree& taskTree,
    std::function<void(const Configuration&)> setter)
{
    const auto taskType = taskTree.get<std::string>("task_type");
    const auto idString = taskTree.get<std::string>("task_id");

    std::stringstream idStringStream{idString};
    boost::uuids::uuid id{};
    idStringStream >> id;

    if (taskType == PingTask::key) {
        return PingTask{id};
    }

    if (taskType == ConfigureTask::key) {
        return ConfigureTask{
            id,
            taskTree.get<double>("dwell"),
            taskTree.get<bool>("running"),
            std::move(setter)
        };
    }

    throw std::logic_error("Illegal task type encountered: " + taskType);
}

Configuration::Configuration(const double meanDwell, const bool isRunning)
    : meanDwell(meanDwell), isRunning(isRunning) {}

PingTask::PingTask(const boost::uuids::uuid& id)
    : id{id} {}

Result PingTask::run() const {
    return Result{id, "PuNG!", true};
}

ConfigureTask::ConfigureTask(
    const boost::uuids::uuid& id,
    double meanDwell,
    bool isRunning,
    std::function<void(const Configuration&)> setter)
    : id{id},
      setter{std::move(setter)},
      meanDwell{meanDwell},
      isRunning{isRunning} {}

Result ConfigureTask::run() const {
    setter(Configuration{meanDwell, isRunning});
    return Result{id, "Configuration successful!", true};
}