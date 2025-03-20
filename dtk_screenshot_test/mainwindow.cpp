#include "mainwindow.h"

// DTK头文件
#include <DTitlebar>
#include <DMessageBox>
#include <DFileDialog>
#include <DApplicationHelper>
#include <DFontSizeManager>

// Qt头文件
#include <QInputMethod>
#include <QSysInfo>
#include <QStandardPaths>

MainWindow::MainWindow(QWidget *parent) : DMainWindow(parent)
{
    // 设置DTK窗口属性
    setAttribute(Qt::WA_DeleteOnClose);
    
    // 设置窗口图标（使用DTK主题图标）
    setWindowIcon(QIcon::fromTheme("deepin-screenshot"));
    
    // 初始化UI
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
    if (screenshotProcess && screenshotProcess->state() == QProcess::Running)
    {
        screenshotProcess->terminate();
        screenshotProcess->waitForFinished(1000);
    }
}

void MainWindow::setupUi()
{
    // 设置窗口标题和大小
    titlebar()->setTitle(tr("截图和输入法测试工具"));
    resize(800, 600);
    
    // 创建中心部件和布局
    QWidget *centralWidget = new QWidget(this);
    setCentralWidget(centralWidget);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);
    mainLayout->setSpacing(10);
    mainLayout->setContentsMargins(20, 10, 20, 20);
    
    // 系统信息标签
    systemInfoLabel = new DLabel(this);
    DFontSizeManager::instance()->bind(systemInfoLabel, DFontSizeManager::T8);
    systemInfoLabel->setForegroundRole(DPalette::TextTips);
    mainLayout->addWidget(systemInfoLabel);
    
    // 截图按钮区域
    QHBoxLayout *buttonLayout = new QHBoxLayout();
    buttonLayout->setSpacing(10);
    
    screenshotButton = new DPushButton(tr("Qt区域截图"), this);
    fullScreenButton = new DPushButton(tr("Qt全屏截图"), this);
    systemScreenshotButton = new DPushButton(tr("系统截图工具"), this);
    saveButton = new DPushButton(tr("保存截图"), this);
    saveButton->setEnabled(false);
    
    // 使用DTK的图标
    screenshotButton->setIcon(QIcon::fromTheme("deepin-screenshot"));
    fullScreenButton->setIcon(QIcon::fromTheme("deepin-screenshot"));
    systemScreenshotButton->setIcon(QIcon::fromTheme("deepin-screen-recorder"));
    saveButton->setIcon(QIcon::fromTheme("document-save"));
    
    buttonLayout->addWidget(screenshotButton);
    buttonLayout->addWidget(fullScreenButton);
    buttonLayout->addWidget(systemScreenshotButton);
    buttonLayout->addWidget(saveButton);
    mainLayout->addLayout(buttonLayout);
    
    // 输入法测试区域
    DGroupBox *inputTestGroup = new DGroupBox(tr("输入法测试"), this);
    QVBoxLayout *inputLayout = new QVBoxLayout(inputTestGroup);
    inputLayout->setSpacing(8);
    
    inputTestField = new DLineEdit(this);
    inputTestField->setPlaceholderText(tr("在此输入中文进行测试..."));
    
    chineseTestArea = new DTextEdit(this);
    chineseTestArea->setPlaceholderText(tr("这里可以测试长文本中文输入..."));
    
    inputMethodLabel = new DLabel(tr("输入法信息: 等待输入..."), this);
    inputMethodLabel->setForegroundRole(DPalette::TextTips);
    
    inputLayout->addWidget(new DLabel(tr("单行输入测试:"), this));
    inputLayout->addWidget(inputTestField);
    inputLayout->addWidget(new DLabel(tr("多行输入测试:"), this));
    inputLayout->addWidget(chineseTestArea);
    inputLayout->addWidget(inputMethodLabel);
    
    mainLayout->addWidget(inputTestGroup);
    
    // 截图显示区域
    DGroupBox *screenshotGroup = new DGroupBox(tr("截图结果"), this);
    QVBoxLayout *screenshotLayout = new QVBoxLayout(screenshotGroup);
    
    screenshotLabel = new DLabel(this);
    screenshotLabel->setAlignment(Qt::AlignCenter);
    screenshotLabel->setMinimumHeight(200);
    screenshotLabel->setText(tr("尚未截图"));
    
    // 添加边框样式
    DPalette pa = DApplicationHelper::instance()->palette(screenshotLabel);
    
    // 直接设置边框样式，不再使用DStyle
    QPalette newPalette = pa;
    newPalette.setBrush(QPalette::Base, newPalette.brush(QPalette::Base));
    screenshotLabel->setPalette(newPalette);
    
    screenshotLayout->addWidget(screenshotLabel);
    mainLayout->addWidget(screenshotGroup);
    
    // 连接信号和槽
    connect(screenshotButton, &DPushButton::clicked, this, &MainWindow::takeScreenshot);
    connect(fullScreenButton, &DPushButton::clicked, this, &MainWindow::fullScreenshot);
    connect(systemScreenshotButton, &DPushButton::clicked, this, &MainWindow::systemScreenshot);
    connect(saveButton, &DPushButton::clicked, this, &MainWindow::saveScreenshot);
    connect(inputTestField, &DLineEdit::textChanged, this, &MainWindow::displayInputMethodInfo);
    connect(chineseTestArea, &DTextEdit::textChanged, this, &MainWindow::displayInputMethodInfo);
}

void MainWindow::takeScreenshot()
{
    // 简单区域截图实现
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

void MainWindow::systemScreenshot()
{
    // 检查系统是否有deepin-screen-recorder工具
    QProcess process;
    process.start("which", QStringList() << "deepin-screen-recorder");
    process.waitForFinished();
    
    if (process.exitCode() != 0) {
        DMessageBox::warning(this, tr("警告"), 
                            tr("未找到系统截图工具(deepin-screen-recorder)\n请先安装或使用Qt截图功能"));
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
    } else {
        // 如果文件不存在，可能是用户取消了截图
        this->setWindowState(Qt::WindowActive);
    }
}

void MainWindow::saveScreenshot()
{
    if (currentScreenshot.isNull()) {
        DMessageBox::warning(this, tr("警告"), tr("没有可保存的截图"));
        return;
    }
    
    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_hhmmss");
    QString defaultPath = QStandardPaths::writableLocation(QStandardPaths::PicturesLocation);
    QString defaultName = QString("%1/screenshot_%2.png").arg(defaultPath).arg(timestamp);
    
    QString filename = DFileDialog::getSaveFileName(
        this, 
        tr("保存截图"), 
        defaultName,
        tr("图像 (*.png *.jpg)")
    );
    
    if (filename.isEmpty()) {
        return;
    }
    
    if (currentScreenshot.save(filename)) {
        DMessageBox::information(this, tr("成功"), 
                                tr("截图已保存到 %1").arg(filename));
    } else {
        DMessageBox::critical(this, tr("错误"), tr("保存截图失败"));
    }
}

void MainWindow::displayInputMethodInfo()
{
    // 显示输入法信息
    QInputMethod *inputMethod = QGuiApplication::inputMethod();
    bool visible = inputMethod->isVisible();
    QString locale = QLocale::system().name();
    
    inputMethodLabel->setText(QString(tr("输入法状态: %1, 当前区域设置: %2"))
                             .arg(visible ? tr("活动") : tr("非活动"))
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
    
    QString systemInfo = QString(tr("CPU架构: %1 | 操作系统: %2 | 内核: %3 %4 | 系统截图工具: %5"))
                            .arg(cpuArchitecture)
                            .arg(osType)
                            .arg(kernelType)
                            .arg(kernelVersion)
                            .arg(hasSystemScreenshot ? tr("可用") : tr("不可用"));
    
    systemInfoLabel->setText(systemInfo);
}
