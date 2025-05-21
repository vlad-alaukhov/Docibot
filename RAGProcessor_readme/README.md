# RAGProcessor

Модуль для работы с RAG-системами с поддержкой CPU и GPU.
**Версии зависимостей строго зафиксированы для гарантии стабильности.**


## Как удалить пакет локально с зависимостями

1. **Полное удаление пакета и артефактов сборки**
   `pip uninstall rag-processor -y`
   `rm -rf ~/RAGProcessor/build ~/RAGProcessor/dist ~/RAGProcessor/*.egg-info`

2. **Удаление зависимостей**
   `pip uninstall -y torch sentence-transformers faiss-gpu langchain-core langchain-community langchain-openai pymupdf pdfminer.six camelot-py python-docx pandas opencv-python-headless tiktoken python-dotenv requests openpyxl numpy`

3. **Очистка кэша pip**
   `pip cache purge`

4. **Для виртуальных окружений**
   Удалите папку окружения и создайте новое:
   `rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate`

**Примечания:**

- Для GPU-зависимостей добавьте: `nvidia-cublas-cu12 nvidia-cuda-runtime-cu12` в команду удаления.
- Если зависимости используются другими пакетами — используйте `pip-autoremove rag-processor -y`.
- Фиксированные версии в `setup.py` могут требовать ручного управления зависимостями.

## Как скомпилировать пакет с опцией -e для разработчика

**Решение:**

1. **Удаление предыдущей версии и артефактов**
   `pip uninstall rag-processor -y`
   `rm -rf ~/RAGProcessor/build ~/RAGProcessor/dist ~/RAGProcessor/*.egg-info`

2. **Очистка зависимостей (опционально)**
   `pip uninstall -y torch sentence-transformers faiss-gpu faiss-cpu langchain-core langchain-community langchain-openai pymupdf pdfminer.six camelot-py python-docx pandas opencv-python-headless tiktoken python-dotenv requests openpyxl numpy`

3. **Установка в режиме разработки**
   Для CPU:
   `pip install -e . --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple`

   Для GPU:
   `pip install -e ~/RAGProcessor[gpu] --extra-index-url https://download.pytorch.org/whl/cu118 --extra-index-url https://pypi.org/simple --extra-index-url https://pypi.nvidia.com`

**Примечания:**
- Режим `-e` создает симлинки, позволяя редактировать код без переустановки.
- Для GPU убедитесь, что CUDA 11.8 установлена и выбрана среда выполнения T4 в Colab.
- При конфликтах: `rm -rf .venv && python -m venv .venv`.
- Фиксированные версии в `setup.py` гарантируют совместимость.

## Как установить пакет с диска в Ваш новый проект

**Для CPU**

`pip install -e ~/Projects/RAGProcessor --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple`


## Как установить пакет для CPU локально из requirements.txt

**Решение:**

1. **Активация виртуального окружения (рекомендуется)**
   `python -m venv .venv && source .venv/bin/activate`

2. **Удаление предыдущих версий (если нужно)**
   `pip uninstall rag-processor -y`

3. **Установка зависимостей**
   `pip install -r requirements.txt`

**Пример содержимого `requirements.txt` для CPU:**
```txt
--index-url https://download.pytorch.org/whl/cpu
torch==2.3.0+cpu
sentence-transformers==2.2.0
faiss-cpu==1.7.0
langchain-core==0.3.51
pymupdf==1.23.0
python-docx==1.1.2
opencv-python-headless==4.11.0.86

**Примечания:**

Если requirements.txt не содержит явных ссылок на CPU-версии, добавьте --index-url для PyTorch.

Для полной изоляции используйте новое виртуальное окружение.

После установки проверьте зависимости:
pip list | grep -E "torch|sentence-transformers|faiss"



