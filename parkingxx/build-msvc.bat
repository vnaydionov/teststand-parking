set YBORM_ROOT=c:\work\yborm-0.4.8-msvc2013
set DEP_LIBS_ROOT=%YBORM_ROOT%\dep_libs_msvc2013
set BOOST_ROOT=%YBORM_ROOT%\boost_1_57_0-mini
set PATH=%PATH%;%YBORM_ROOT%\bin;%DEP_LIBS_ROOT%\bin;%BOOST_ROOT%\lib32-msvc-12.0

set BAT_DIR=%~dp0
cmake -G "NMake Makefiles" -D CMAKE_INSTALL_PREFIX:PATH=%BAT_DIR%..\teststand-parking.inst -D DEP_LIBS_ROOT:PATH=%DEP_LIBS_ROOT% -D BOOST_ROOT:PATH=%BOOST_ROOT% -D USE_QT:STRING=%USE_QT% -D YBORM_ROOT:PATH=%YBORM_ROOT% %BAT_DIR%..\teststand-parking\parkingxx
rem nmake && nmake install
jom && jom install
