"""
信息提取模块 - 从多个来源提取原始数据

支持的信息源：
- 网页链接（HTML）
- PDF 文件
- 图片文件（通过OCR）
- 纯文本
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pyzbar import pyzbar
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

from config import settings, SUPPORTED_FORMATS

# 配置日志
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """信息源类型"""
    URL = "url"
    FILE = "file"
    TEXT = "text"
    PDF = "pdf"
    IMAGE = "image"


@dataclass
class ExtractionResult:
    """信息提取结果"""
    source_type: SourceType
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    extracted_text: str = ""
    extracted_images: List[Dict[str, str]] = field(default_factory=list)
    extracted_qr_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['source_type'] = self.source_type.value
        return data
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class InformationExtractor:
    """信息提取器"""
    
    def __init__(self, enable_ocr: bool = False, enable_qr: bool = False):
        """
        初始化提取器
        
        Args:
            enable_ocr: 是否启用OCR
            enable_qr: 是否启用二维码识别
        """
        self.enable_ocr = enable_ocr and TESSERACT_AVAILABLE
        self.enable_qr = enable_qr and QR_AVAILABLE
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': settings.USER_AGENT
        })
        
        if self.enable_ocr:
            pytesseract.pytesseract.pytesseract_cmd = settings.TESSERACT_CMD
            logger.info("✓ OCR 已启用")
        
        if not self.enable_ocr:
            logger.info("⚠ OCR 未启用 (需要安装 Tesseract)")
        
        if not self.enable_qr:
            logger.info("⚠ 二维码识别未启用 (需要安装 pyzbar)")
    
    async def extract(self, source: Union[str, Path]) -> ExtractionResult:
        """
        从来源提取信息（主入口）
        
        Args:
            source: 信息源（URL、文件路径或纯文本）
        
        Returns:
            ExtractionResult: 提取结果
        """
        logger.info(f"开始提取信息: {source[:50]}...")
        
        # 判断信息源类型
        if isinstance(source, str):
            if source.startswith(('http://', 'https://')):
                return await self._extract_from_url(source)
            elif Path(source).exists():
                return await self._extract_from_file(source)
            else:
                return await self._extract_from_text(source)
        elif isinstance(source, Path):
            return await self._extract_from_file(str(source))
        
        return ExtractionResult(
            source_type=SourceType.TEXT,
            error="不支持的信息源类型"
        )
    
    async def _extract_from_url(self, url: str) -> ExtractionResult:
        """从URL提取信息"""
        logger.info(f"从URL提取: {url}")
        
        try:
            # 发送请求
            response = self.session.get(
                url,
                timeout=settings.REQUEST_TIMEOUT,
                allow_redirects=True
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取文本
            text = self._extract_text_from_html(soup)
            
            # 提取图片
            images = await self._extract_images_from_html(soup, url)
            
            # 提取二维码
            qr_codes = []
            if self.enable_qr:
                for img_data in images:
                    qr_codes.extend(self._extract_qr_from_image(img_data['path']))
            
            result = ExtractionResult(
                source_type=SourceType.URL,
                source_url=url,
                extracted_text=text,
                extracted_images=images,
                extracted_qr_codes=qr_codes,
                metadata={
                    'title': self._extract_title(soup),
                    'description': self._extract_meta_description(soup),
                    'content_type': response.headers.get('content-type', ''),
                }
            )
            
            logger.info(f"✓ 成功提取 {len(text)} 字符")
            return result
            
        except requests.RequestException as e:
            logger.error(f"✗ 网络请求错误: {e}")
            return ExtractionResult(
                source_type=SourceType.URL,
                source_url=url,
                error=f"网络请求错误: {str(e)}"
            )
        except Exception as e:
            logger.error(f"✗ 提取失败: {e}")
            return ExtractionResult(
                source_type=SourceType.URL,
                source_url=url,
                error=f"提取失败: {str(e)}"
            )
    
    def _extract_text_from_html(self, soup: BeautifulSoup) -> str:
        """从HTML中提取文本"""
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 获取文本
        text = soup.get_text()
        
        # 清理空白
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:10000]  # 限制长度
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        title = soup.find('title')
        if title:
            return title.get_text().strip()
        
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        return ""
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """提取元描述"""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            return meta.get('content', '')
        return ""
    
    async def _extract_images_from_html(
        self, 
        soup: BeautifulSoup, 
        base_url: str
    ) -> List[Dict[str, str]]:
        """从HTML中提取图片"""
        images = []
        
        if not self.enable_ocr:
            return images
        
        img_tags = soup.find_all('img')[:5]  # 限制前5张图片
        
        for idx, img_tag in enumerate(img_tags):
            try:
                img_url = img_tag.get('src', '')
                if not img_url:
                    continue
                
                # 处理相对URL
                if img_url.startswith('/'):
                    from urllib.parse import urljoin
                    img_url = urljoin(base_url, img_url)
                
                # 下载图片
                img_response = self.session.get(
                    img_url,
                    timeout=10,
                    stream=True
                )
                img_response.raise_for_status()
                
                # 保存图片
                img = Image.open(BytesIO(img_response.content))
                img_path = settings.TEMP_DIR / f"image_{idx}.png"
                img.save(img_path)
                
                # OCR识别
                ocr_text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                
                images.append({
                    'path': str(img_path),
                    'url': img_url,
                    'ocr_text': ocr_text,
                })
                
                logger.info(f"✓ 识别图片 {idx+1}: 提取 {len(ocr_text)} 字符")
                
            except Exception as e:
                logger.warning(f"⚠ 图片处理失败: {e}")
                continue
        
        return images
    
    def _extract_qr_from_image(self, image_path: str) -> List[str]:
        """从图片中提取二维码"""
        qr_codes = []
        
        if not self.enable_qr:
            return qr_codes
        
        try:
            img = Image.open(image_path)
            decoded = pyzbar.decode(img)
            
            for obj in decoded:
                qr_codes.append(obj.data.decode('utf-8'))
            
            if qr_codes:
                logger.info(f"✓ 识别 {len(qr_codes)} 个二维码")
        
        except Exception as e:
            logger.warning(f"⚠ 二维码识别失败: {e}")
        
        return qr_codes
    
    async def _extract_from_file(self, file_path: str) -> ExtractionResult:
        """从文件提取信息"""
        logger.info(f"从文件提取: {file_path}")
        
        path = Path(file_path)
        
        # 检查文件是否存在
        if not path.exists():
            return ExtractionResult(
                source_type=SourceType.FILE,
                source_file=file_path,
                error=f"文件不存在: {file_path}"
            )
        
        # 检查文件大小
        file_size = path.stat().st_size / (1024 * 1024)  # MB
        if file_size > settings.MAX_FILE_SIZE:
            return ExtractionResult(
                source_type=SourceType.FILE,
                source_file=file_path,
                error=f"文件过大: {file_size:.2f}MB (限制: {settings.MAX_FILE_SIZE}MB)"
            )
        
        suffix = path.suffix.lower()
        
        try:
            if suffix == '.txt' or suffix == '.md':
                return await self._extract_from_text_file(file_path)
            elif suffix == '.pdf':
                return await self._extract_from_pdf(file_path)
            elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                return await self._extract_from_image_file(file_path)
            else:
                return ExtractionResult(
                    source_type=SourceType.FILE,
                    source_file=file_path,
                    error=f"不支持的文件格式: {suffix}"
                )
        
        except Exception as e:
            logger.error(f"✗ 文件处理失败: {e}")
            return ExtractionResult(
                source_type=SourceType.FILE,
                source_file=file_path,
                error=f"文件处理失败: {str(e)}"
            )
    
    async def _extract_from_text_file(self, file_path: str) -> ExtractionResult:
        """从文本文件提取"""
        logger.info(f"读取文本文件: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        logger.info(f"✓ 成功提取 {len(text)} 字符")
        
        return ExtractionResult(
            source_type=SourceType.TEXT,
            source_file=file_path,
            extracted_text=text,
        )
    
    async def _extract_from_pdf(self, file_path: str) -> ExtractionResult:
        """从PDF提取信息"""
        logger.info(f"处理PDF文件: {file_path}")
        
        try:
            import PyPDF2
        except ImportError:
            return ExtractionResult(
                source_type=SourceType.PDF,
                source_file=file_path,
                error="需要安装 PyPDF2: pip install PyPDF2"
            )
        
        text = ""
        try:
            with open(file_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                for page in reader.pages[:10]:  # 限制前10页
                    text += page.extract_text()
            
            logger.info(f"✓ PDF提取成功: {len(text)} 字符")
            
            return ExtractionResult(
                source_type=SourceType.PDF,
                source_file=file_path,
                extracted_text=text,
            )
        
        except Exception as e:
            logger.error(f"✗ PDF处理失败: {e}")
            return ExtractionResult(
                source_type=SourceType.PDF,
                source_file=file_path,
                error=f"PDF处理失败: {str(e)}"
            )
    
    async def _extract_from_image_file(self, file_path: str) -> ExtractionResult:
        """从图片文件提取信息"""
        logger.info(f"处理图片文件: {file_path}")
        
        images = []
        qr_codes = []
        
        try:
            img = Image.open(file_path)
            
            # OCR识别
            ocr_text = ""
            if self.enable_ocr:
                ocr_text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                logger.info(f"✓ OCR识别: {len(ocr_text)} 字符")
            
            # 二维码识别
            if self.enable_qr:
                decoded = pyzbar.decode(img)
                for obj in decoded:
                    qr_codes.append(obj.data.decode('utf-8'))
                
                if qr_codes:
                    logger.info(f"✓ 识别 {len(qr_codes)} 个二维码")
            
            images.append({
                'path': file_path,
                'ocr_text': ocr_text,
            })
            
            return ExtractionResult(
                source_type=SourceType.IMAGE,
                source_file=file_path,
                extracted_text=ocr_text,
                extracted_images=images,
                extracted_qr_codes=qr_codes,
            )
        
        except Exception as e:
            logger.error(f"✗ 图片处理失败: {e}")
            return ExtractionResult(
                source_type=SourceType.IMAGE,
                source_file=file_path,
                error=f"图片处理失败: {str(e)}"
            )
    
    async def _extract_from_text(self, text: str) -> ExtractionResult:
        """从纯文本提取"""
        logger.info(f"处理纯文本: {len(text)} 字符")
        
        return ExtractionResult(
            source_type=SourceType.TEXT,
            extracted_text=text,
        )


# 便捷函数
async def extract_information(source: Union[str, Path]) -> ExtractionResult:
    """
    快速提取信息
    
    Args:
        source: 信息源
    
    Returns:
        ExtractionResult: 提取结果
    """
    extractor = InformationExtractor(
        enable_ocr=settings.ENABLE_OCR,
        enable_qr=settings.ENABLE_QR_CODE,
    )
    return await extractor.extract(source)


if __name__ == "__main__":
    # 测试
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            source = sys.argv[1]
            result = await extract_information(source)
            print(result.to_json())
        else:
            print("用法: python information_extraction.py <url|file_path|text>")
    
    asyncio.run(main())
