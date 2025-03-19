#include "mainwindow.h"
#include <QApplication>
#include <QScreen>
#include <QPixmap>
#include <QFileDialog>
#include <QMessageBox>
#include <QInputMethod>
#include <QProcess>
#include <QSysInfo>
#include <QDir>
#include <QFile>

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent)
{
    setupUi();
    displaySystemInfo();
    
    // 初始化截图进程
    screenshotProcess = new QProcess(this);
    connect(screenshotProcess, static_cast<void(QProcess::*)(int, QProcess::ExitStatus)>(&QProcess::finished), 
            this, &MainWindow::checkScreenshotResult);
    
    // 创建临时保存路径
    QDir tempDir = QDir::temp();
    screenshotSavePath = tempDir.filePath("screenshot_temp.png");
}

MainWindow::~MainWindow()
{
    if (screenshotProcess)
    {
        if (screenshotProcess->state() == QProcess::Running)
        {
            screenshotProcess->terminate();
            screenshotProcess->waitForFinished(1000);
        }
    }
}

void MainWindow::setupUi()
{
    // 设置窗口标题和大小
    setWindowTitle("截图和输入法测试工具");
    resize(800, 600);
    
    // 创建中心部件和布局
    QWidget *centralWidget = new QWidget(this);
    setCentralWidget(centralWidget);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);
    
    // 系统信息标签
    systemInfoLabel = new QLabel(this);
    systemInfoLabel->setFrameStyle(QFrame::Panel | QFrame::Sunken);
    mainLayout->addWidget(systemInfoLabel);
    
    // 截图按钮区域
    QHBoxLayout *buttonLayout = new QHBoxLayout();
    screenshotButton = new QPushButton("Qt区域截图", this);
    fullScreenButton = new QPushButton("Qt全屏截图", this);
    QPushButton *systemScreenshotButton = new QPushButton("系统截图工具", this);
    saveButton = new QPushButton("保存截图", this);
    saveButton->setEnabled(false);
    
    buttonLayout->addWidget(screenshotButton);
    buttonLayout->addWidget(fullScreenButton);
    buttonLayout->addWidget(systemScreenshotButton);
    buttonLayout->addWidget(saveButton);
    mainLayout->addLayout(buttonLayout);
    
    // 输入法测试区域
    QGroupBox *inputTestGroup = new QGroupBox("输入法测试", this);
    QVBoxLayout *inputLayout = new QVBoxLayout(inputTestGroup);
    
    inputTestField = new QLineEdit(this);
    inputTestField->setPlaceholderText("在此输入中文进行测试...");
    
    chineseTestArea = new QTextEdit(this);
    chineseTestArea->setPlaceholderText("这里可以测试长文本中文输入...");
    
    inputMethodLabel = new QLabel("输入法信息: 等待输入...", this);
    
    inputLayout->addWidget(new QLabel("单行输入测试:"));
    inputLayout->addWidget(inputTestField);
    inputLayout->addWidget(new QLabel("多行输入测试:"));
    inputLayout->addWidget(chineseTestArea);
    inputLayout->addWidget(inputMethodLabel);
    
    mainLayout->addWidget(inputTestGroup);
    
    // 截图显示区域
    QGroupBox *screenshotGroup = new QGroupBox("截图结果", this);
    QVBoxLayout *screenshotLayout = new QVBoxLayout(screenshotGroup);
    
    screenshotLabel = new QLabel(this);
    screenshotLabel->setAlignment(Qt::AlignCenter);
    screenshotLabel->setMinimumHeight(200);
    screenshotLabel->setFrameStyle(QFrame::StyledPanel);
    screenshotLabel->setText("尚未截图");
    
    screenshotLayout->addWidget(screenshotLabel);
    
    mainLayout->addWidget(screenshotGroup);
    
    // 连接信号和槽
    connect(screenshotButton, &QPushButton::clicked, this, &MainWindow::takeScreenshot);
    connect(fullScreenButton, &QPushButton::clicked, this, &MainWindow::fullScreenshot);
    connect(systemScreenshotButton, &QPushButton::clicked, this, &MainWindow::systemScreenshot);
    connect(saveButton, &QPushButton::clicked, this, &MainWindow::saveScreenshot);
    connect(inputTestField, &QLineEdit::textChanged, this, &MainWindow::displayInputMethodInfo);
    connect(chineseTestArea, &QTextEdit::textChanged, this, &MainWindow::displayInputMethodInfo);
}

void MainWindow::takeScreenshot()
{
    // 简单区域截图实现 - 此处仅捕获当前窗口
    this->setWindowState(Qt::WindowMinimized);
    
    // 给用户一些时间来选择想要截图的窗口
    QTimer::singleShot(1000, this, [=]() {
        QScreen *screen = QGuiApplication::primaryScreen();
        currentScreenshot = screen->grabWindow(0, this->x(), this->y(), this->width(), this->height());
        
        // 显示截图
        QPixmap scaledPixmap = currentScreenshot.scaled(screenshotLabel->size(), 
                                                       Qt::KeepAspectRatio, 
                                                       Qt::SmoothTransformation);
        screenshotLabel->setPixmap(scaledPixmap);
        saveButton->setEnabled(true);
        
        // 恢复窗口状态
        this->setWindowState(Qt::WindowActive);
    });
}

void MainWindow::fullScreenshot()
{
    // 最小化窗口
    this->setWindowState(Qt::WindowMinimized);
    
    // 等待窗口最小化
    QTimer::singleShot(500, this, [=]() {
        QScreen *screen = QGuiApplication::primaryScreen();
        currentScreenshot = screen->grabWindow(0);
        
        // 显示截图
        QPixmap scaledPixmap = currentScreenshot.scaled(screenshotLabel->size(), 
                                                       Qt::KeepAspectRatio, 
                                                       Qt::SmoothTransformation);
        screenshotLabel->setPixmap(scaledPixmap);
        saveButton->setEnabled(true);
        
        // 恢复窗口状态
        this->setWindowState(Qt::WindowActive);
    });
}

void MainWindow::saveScreenshot()
{
    if (currentScreenshot.isNull()) {
        QMessageBox::warning(this, "警告", "没有可保存的截图");
        return;
    }
    
    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_hhmmss");
    QString filename = QFileDialog::getSaveFileName(this, "保存截图", 
                                                   QString("screenshot_%1.png").arg(timestamp),
                                                   "图像 (*.png *.jpg)");
    
    if (filename.isEmpty()) {
        return;
    }
    
    if (currentScreenshot.save(filename)) {
        QMessageBox::information(this, "成功", QString("截图已保存到 %1").arg(filename));
    } else {
        QMessageBox::critical(this, "错误", "保存截图失败");
    }
}

void MainWindow::displayInputMethodInfo()
{
    // 显示输入法信息
    QInputMethod *inputMethod = QGuiApplication::inputMethod();
    bool visible = inputMethod->isVisible();
    QString locale = QLocale::system().name();
    
    inputMethodLabel->setText(QString("输入法状态: %1, 当前区域设置: %2")
                             .arg(visible ? "活动" : "非活动")
                             .arg(locale));
}

void MainWindow::displaySystemInfo()
{
    // 获取系统信息
    QString cpuArchitecture = QSysInfo::currentCpuArchitecture();
    QString osType = QSysInfo::prettyProductName();
    QString kernelType = QSysInfo::kernelType();
    QString kernelVersion = QSysInfo::kernelVersion();
    
    // 检查deepin-screen-recorder是否存在
    QProcess process;
    process.start("which", QStringList() << "deepin-screen-recorder");
    process.waitForFinished();
    bool hasSystemScreenshot = (process.exitCode() == 0);
    
    QString systemInfo = QString("CPU架构: %1 | 操作系统: %2 | 内核: %3 %4 | 系统截图工具: %5")
                            .arg(cpuArchitecture)
                            .arg(osType)
                            .arg(kernelType)
                            .arg(kernelVersion)
                            .arg(hasSystemScreenshot ? "可用" : "不可用");
    
    systemInfoLabel->setText(systemInfo);
}

void MainWindow::systemScreenshot()
{
    // 检查系统是否有deepin-screen-recorder工具
    QProcess process;
    process.start("which", QStringList() << "deepin-screen-recorder");
    process.waitForFinished();
    
    if (process.exitCode() != 0) {
        QMessageBox::warning(this, "警告", "未找到系统截图工具(deepin-screen-recorder)\n请先安装或使用Qt截图功能");
        return;
    }
    
    // 最小化当前窗口
    this->setWindowState(Qt::WindowMinimized);
    
    // 等待窗口最小化
    QTimer::singleShot(500, this, [=]() {
        // 准备命令行参数
        QStringList arguments;
        arguments << "--save-path" << screenshotSavePath;
        
        // 启动系统截图工具
        screenshotProcess->start("deepin-screen-recorder", arguments);
    });
}

void MainWindow::checkScreenshotResult(int exitCode, QProcess::ExitStatus exitStatus)
{
    // 检查截图是否成功
    if (exitCode != 0 || exitStatus != QProcess::NormalExit) {
        // 若进程异常结束，恢复窗口并返回
        this->setWindowState(Qt::WindowActive);
        return;
    }
    
    QFile file(screenshotSavePath);
    if (file.exists()) {
        // 加载截图
        currentScreenshot = QPixmap(screenshotSavePath);
        
        // 显示截图
        QPixmap scaledPixmap = currentScreenshot.scaled(screenshotLabel->size(), 
                                                       Qt::KeepAspectRatio, 
                                                       Qt::SmoothTransformation);
        screenshotLabel->setPixmap(scaledPixmap);
        saveButton->setEnabled(true);
        
        // 恢复窗口状态
        this->setWindowState(Qt::WindowActive);
        
        // 可选：删除临时文件
        // file.remove();
    } else {
        // 如果文件不存在，可能是用户取消了截图
        this->setWindowState(Qt::WindowActive);
    }
}
