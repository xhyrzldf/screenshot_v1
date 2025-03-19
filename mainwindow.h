#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QScreen>
#include <QPixmap>
#include <QPushButton>
#include <QLineEdit>
#include <QTextEdit>
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QTimer>
#include <QDateTime>
#include <QGroupBox>
#include <QProcess>
#include <QDir>
#include <QFile>

class MainWindow : public QMainWindow
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
    
    // UI 组件
    QPushButton *screenshotButton;
    QPushButton *fullScreenButton;
    QPushButton *saveButton;
    QLineEdit *inputTestField;
    QTextEdit *chineseTestArea;
    QLabel *screenshotLabel;
    QLabel *inputMethodLabel;
    QLabel *systemInfoLabel;
    
    void setupUi();
    void displaySystemInfo();
};

#endif // MAINWINDOW_H
