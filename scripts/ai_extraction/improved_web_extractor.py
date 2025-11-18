"""
改进的信息提取器 - 支持图片 OCR 识别
"""

import asyncio
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from typing import Optional, List, Tuple

class ImprovedWebExtractor:
    """改进的网页提取器 - 支持图片文本识别"""
    
    def __init__(self, enable_ocr: bool = True):
        self.enable_ocr = enable_ocr
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    async def extract_from_url(self, url: str) -> Tuple[str, List[str]]:
        """
        从 URL 提取文本和图片中的文字
        
        Returns:
            (完整文本, 从图片中识别的文字列表)
        """
        try:
            response = self.session.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
        except Exception as e:
            return f"无法访问 URL: {str(e)}", []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 第 1 步：提取普通文本
        text_content = self._extract_text(soup)
        
        # 第 2 步：从图片中提取文字（如果启用 OCR）
        image_texts = []
        if self.enable_ocr:
            image_texts = await self._extract_text_from_images(url, soup)
        
        # 合并文本
        all_text = text_content
        if image_texts:
            all_text += "\n\n【图片中的文字】\n" + "\n".join(image_texts)
        
        return all_text, image_texts
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """提取 HTML 中的纯文本"""
        
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 提取文本
        text = soup.get_text()
        
        # 清理空白
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    async def _extract_text_from_images(self, base_url: str, soup: BeautifulSoup) -> List[str]:
        """从网页中的图片提取文字"""
        
        image_texts = []
        
        # 找到所有图片
        img_tags = soup.find_all('img', limit=10)  # 最多处理 10 张图片
        
        for idx, img_tag in enumerate(img_tags):
            try:
                # 获取图片 URL
                img_url = img_tag.get('src')
                if not img_url:
                    continue
                
                # 处理相对 URL
                if not img_url.startswith('http'):
                    from urllib.parse import urljoin
                    img_url = urljoin(base_url, img_url)
                
                # 下载图片
                img_response = self.session.get(img_url, timeout=5)
                img_response.raise_for_status()
                
                # 打开图片
                img = Image.open(BytesIO(img_response.content))
                
                # OCR 识别
                text = await self._ocr_image(img)
                
                if text and text.strip():
                    image_texts.append(f"【图片 {idx + 1}】\n{text}")
            
            except Exception as e:
                pass  # 忽略单个图片的错误
        
        return image_texts
    
    async def _ocr_image(self, img: Image.Image) -> str:
        """对图片进行 OCR 识别"""
        
        try:
            import pytesseract
            
            # 识别文字
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            return text
        
        except ImportError:
            return ""
        except Exception as e:
            return ""


async def extract_with_ocr(url: str, fallback_text: str = "") -> str:
    """
    从 URL 提取信息，支持从图片识别文字
    """
    
    extractor = ImprovedWebExtractor(enable_ocr=True)
    
    try:
        text, image_texts = await extractor.extract_from_url(url)
        return text
    except:
        return fallback_text
