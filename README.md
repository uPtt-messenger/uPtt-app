# PTT 即時通訊器

這是一個使用 Python 開發的終端機介面（TUI）應用程式，讓使用者可以透過 PTT 的內建站內信系統與另一位使用者進行**即時聊天**。

## 需求

- Python 3.7 或更高版本
- 一個有效的 PTT 帳號

## 安裝

1.  複製此專案：
    ```bash
    git clone <repository_url>
    cd uptt-poc
    ```

2.  安裝所需的套件：
    ```bash
    pip install -r requirements.txt
    ```

## 使用方式

1.  在終端機中執行應用程式：
    ```bash
    python src/app.py
    ```

2.  依照提示輸入您的 PTT ID 與密碼以登入。

3.  輸入您想對話的使用者 ID。

4.  成功後，即可開始聊天。在輸入區輸入訊息後按 `Enter` 即可發送。

5.  若要離開程式，請在輸入區輸入 `exit` 並按 `Enter`，或直接按下 `Ctrl+C`。

## 檔案結構

```
/Users/codingman/git/uptt-poc/
├───.gitignore
├───requirements.txt
├───src/
│   ├───app.py         # 主應用程式邏輯
│   ├───config.py      # 應用程式設定
│   ├───contant.py     # 常數定義
│   └───utils.py       # 工具函式
└───...
```
