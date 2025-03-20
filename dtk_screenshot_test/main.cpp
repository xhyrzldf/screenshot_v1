#include "mainwindow.h"
#include <DApplication>
#include <DWidgetUtil>
#include <DGuiApplicationHelper>

DWIDGET_USE_NAMESPACE

int main(int argc, char *argv[])
{
    // 使用DTK的应用程序框架
    DApplication app(argc, argv);
    
    // 设置应用程序信息（符合DTK命名规范）
    app.setOrganizationName("deepin");
    app.setApplicationName("deepin-screenshot-test");
    app.setApplicationVersion("1.0");
    app.setProductName(QObject::tr("截图和输入法测试工具"));
    app.setApplicationDescription(QObject::tr("一个用于测试截图功能和中文输入法的工具"));
    
    // 加载翻译
    app.loadTranslator();
    
    // 应用DTK风格设置 - 使用新的API
    DGuiApplicationHelper::instance()->setPaletteType(DGuiApplicationHelper::instance()->themeType());
    // 已弃用的API已移除
    
    // 创建主窗口
    MainWindow mainWindow;
    mainWindow.show();
    
    // 将窗口移动到屏幕中央
    Dtk::Widget::moveToCenter(&mainWindow);
    
    return app.exec();
}
