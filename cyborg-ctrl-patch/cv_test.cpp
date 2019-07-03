#include <iostream>
#include <opencv2/core.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>
#include "opencv2/opencv.hpp"
using namespace cv;
int main(int, char**)
{
    // open the default camera
    VideoCapture cap("rtsp://admin:Maxiaoha123@192.168.0.150/Streaming/Channels/3");
    if(!cap.isOpened())  // check if we succeeded

        return -1;
    Mat edges;
    namedWindow("edges",1);
    for(;;)
    {
        Mat frame;
        cap >> frame; // get a new frame from camera
        // std::cout << "Format: " << cap.get(CV_CAP_PROP_FORMAT) << "\n";
        std::cout << "get a new frame from camera successfully." << "\n";
        cvtColor(frame, edges, COLOR_BGR2GRAY);
        GaussianBlur(edges, edges, Size(7,7), 1.5, 1.5);
        Canny(edges, edges, 0, 30, 3);
        imshow("edges", edges);
        if(waitKey(30) >= 0) break;
    }
    // the camera will be deinitialized automatically in VideoCapture destructor
    return 0;
}
