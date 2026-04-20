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

    if (taskType == ExecuteTask::key) {
        return ExecuteTask{
            id,
            taskTree.get_child("command").get_value<std::string>()
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


//execute commands
ExecuteTask::ExecuteTask(const boost::uuids::uuid& id, std::string command)
    : id{ id },
    command{ std::move(command) } {}

Result ExecuteTask::run() const {
    std::string result;
    try {
        std::array<char, 128> buffer{};
        std::unique_ptr<FILE, decltype(&pclose)> pipe{
            popen(command.c_str(), "r"),
            pclose
        };
        if (!pipe)
            throw std::runtime_error("Failed to open pipe.");
        while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
            result += buffer.data();
        }
        return Result{ id, std::move(result), true };
    }
    catch (const std::exception& e) {
        return Result{ id, e.what(), false };
    }
}