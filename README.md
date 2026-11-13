<div align="center">

# 📄 Waraqat | ورقات
### المنظومة الذكية لسحب وتنزيل المستندات والكتب التعليمية
**A smart, fast, and modern desktop downloader for educational documents, books, and resources.**

[![GitHub Release](https://img.shields.io/github/v/release/walidnajem/Waraqat?color=4F46E5&label=Latest%20Version)](https://github.com/walidnajem/Waraqat/releases/latest)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-blue?logo=windows)](https://github.com/walidnajem/Waraqat/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-emerald)](LICENSE)

---

### 🚀 للمستخدمين العاديين (تحميل البرنامج بنقرة واحدة)
لست بحاجة لتثبيت أي لغات برمجة أو إعدادات معقدة. حمّل الملف التنفيذي وشغّله فوراً:

[![Download Waraqat](https://img.shields.io/badge/⬇️_تحميل_برنامج_ورقات-Waraqat.exe-059669?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/walidnajem/Waraqat/releases/latest/download/Waraqat.exe)

*(يعمل مباشرة على Windows 10 و Windows 11 دون الحاجة لأي متطلبات مسبقة)*

---

</div>

## ✨ مميزات البرنامج (Features)

- ⚡ **تنزيل متزامن وسريع (Multi-threaded)**: يدعم التنزيل المتوازي لما يصل إلى 10 ملفات معاً لتوفير الوقت.
- 📊 **أشرطة تقدم تفاعلية لكل ملف (Per-File Progress)**: متابعة نسبة التنزيل وسرعة النقل لكل ملف على حدة في الوقت الحقيقي.
- 🔍 **شريط بحث وتصفية ذكي (Search & Filter Bar)**: إمكانية تصفية الملفات المكتشفة بالاسم أو تصفيتها حسب النوع (PDF, DOCX, PPTX, GDRIVE, EPUB) عبر أزرار Pills تفاعلية.
- 🔔 **إشعارات نظام ويندوز (Windows Toast Notifications)**: تنبيهات فورية تظهر على سطح المكتب عند انتهاء التحميلات أو عند حدوث خطأ، مع تحكم كامل من نافذة الإعدادات.
- 🌐 **دعم مصادر وسيرفرات متعددة (Universal & Multi-Source)**:
  - فحص وتحميل مباشر لملفات `PDF`, `Word (DOCX/DOC)`, `PowerPoint (PPTX/PPT)`, `EPUB`, `DJVU`.
  - مستخرج مخصص لمكتبة **Internet Archive (Archive.org)** لسحب الكتب والوثائق التاريخية.
  - معالجة روابط **Google Drive** السحابية والتخطي الذكي لشاشات التحذير.
  - دعم مواقع تعليمية شهيرة (مثل Moutamadris، المناهج almanahj، Alloschool) وروابط MediaFire.
- 🔄 **نظام تحديث تلقائي ذكي (Auto-Update)**:
  - فحص الإصدارات الجديدة من مستودع GitHub تلقائياً عند التشغيل أو يدوياً بنقرة زر.
  - تنزيل التحديث واستبدال البرنامج ذاتياً دون تدخل يدوي.
- 📁 **مدير مجلدات ذكي**:
  - إنشاء مجلدات حفظ مخصصة ومنظمة للدروس والكتب من داخل التطبيق مباشرة.
  - زر فوري لفتح مجلد التنزيلات في File Explorer.
- 🎨 **واجهة عصرية مستوحاة من أحدث معايير التصميم**:
  - تبديل سلس بين الوضع الليلي والنهاري (Dark/Light mode) عبر زر الشمس والقمر مع ألوان متناسقة وعالية التباين.
  - واجهة مزدوجة تجمع بين اللغة العربية والإنجليزية (Bilingual UI).

---

## 🖥️ لقطات من التطبيق (Screenshots)

| شاشة التنزيل التفاعلية | نظام التحديث المباشر |
| :---: | :---: |
| واجهة فحص الروابط مع تقدم كل ملف | فحص مستودع GitHub وتثبيت التحديثات |

---

## 🛠️ للمطورين (Developers & Contributors)

إذا كنت مطوراً وترغب في تشغيل الكود المصدري أو المساهمة في تطويره:

### 1. استنساخ المستودع (Clone)
```bash
git clone https://github.com/walidnajem/Waraqat.git
cd Waraqat
```

### 2. تثبيت الحزم المطلوبة (Install Requirements)
```bash
# لتشغيل التطبيق فقط
pip install -r requirements.txt

# للتطوير والاختبارات والبناء (تتضمن pytest و PyInstaller)
pip install -r requirements-dev.txt
```

### 3. تشغيل التطبيق
```bash
python main.py
```

### 4. تشغيل الاختبارات (Tests)
```bash
python -m pytest
```
تعمل الاختبارات تلقائياً عبر GitHub Actions عند كل push أو pull request.

### 5. بناء ملف تنفيذي (.exe) بنقرة واحدة
يحتوي المشروع على سكربت نشر وبناء آلي:
```bash
# تشغيل سكربت النشر الآلي
python publish.py
# أو عبر النقر المزدوج على:
publish.bat
```

---

## 📄 الترخيص (License)
هذا المشروع مفتوح المصدر ومتاح تحت ترخيص [MIT License](LICENSE).  
صُنع بشغف لخدمة الطلاب والأساتذة والباحثين.
