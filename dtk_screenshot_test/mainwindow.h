#ifndef MAINWINDOW_H
#define MAINWINDOW_H

// DTK头文件
#include <DMainWindow>
#include <DPushButton>
#include <DLineEdit>
#include <DTextEdit>
#include <DLabel>
#include <DGroupBox>

// Qt头文件
#include <QScreen>
#include <QPixmap>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QTimer>
#include <QDateTime>
#include <QProcess>
#include <QDir>
#include <QFile>

// 使用DTK命名空间
DWIDGET_USE_NAMESPACE

class MainWindow : public DMainWindow
{
    Q_OBJECT
    
public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();
    
private slots:
    void takeScreenshot();
    void fullScreenshot();
    void systemScreenshot();
    void checkScreenshotResult(int exitCode, QProcess::ExitStatus exitStatus);
    void saveScreenshot();
    void displayInputMethodInfo();
    
private:
    QPixmap currentScreenshot;
    QString screenshotSavePath;
    QProcess *screenshotProcess;
    
    // UI 组件 (使用DTK控件)
    DPushButton *screenshotButton;
    DPushButton *fullScreenButton;
    DPushButton *systemScreenshotButton;
    DPushButton *saveButton;
    DLineEdit *inputTestField;
    DTextEdit *chineseTestArea;
    DLabel *screenshotLabel;
    DLabel *inputMethodLabel;
    DLabel *systemInfoLabel;
    
    void setupUi();
    void displaySystemInfo();
};

#endif // MAINWINDOW_H
