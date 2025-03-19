#include "mainwindow.h"
#include <QApplication>
#include <QLocale>
#include <QTranslator>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    
    // 设置应用程序名称和组织信息
    QApplication::setApplicationName("Screenshot Input Test");
    QApplication::setOrganizationName("Test Organization");
    
    // 支持中文输入法
    QTranslator translator;
    const QStringList uiLanguages = QLocale::system().uiLanguages();
    for (const QString &locale : uiLanguages) {
        const QString baseName = "screenshot_test_" + QLocale(locale).name();
        if (translator.load(":/i18n/" + baseName)) {
            app.installTranslator(&translator);
            break;
        }
    }
    
    MainWindow mainWindow;
    mainWindow.show();
    
    return app.exec();
}
