QT += core gui widgets
# 添加DTK依赖
CONFIG += c++11 link_pkgconfig
PKGCONFIG += dtkwidget dtkgui dtkcore

TARGET = dtk-screenshot-test
TEMPLATE = app

SOURCES += \
    main.cpp \
    mainwindow.cpp

HEADERS += \
    mainwindow.h
