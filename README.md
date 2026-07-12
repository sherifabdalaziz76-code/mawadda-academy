
# أكاديمية المودة — Currency, Codes & Parent Requests

نسخة تشغيلية أولى تشمل:
- تسجيل الدخول والصلاحيات: Admin / Teacher / Parent
- الطلاب وأولياء الأمور والمعلمين
- بيانات الاتصال: هاتف / بريد / واتساب
- الحلقات وربط الطلاب
- حصص بمدة مختلفة بالدقائق
- تسجيل الحضور
- تقييم المعلم للطالب
- تقييم ولي الأمر للمعلم
- ملف الطالب وسجل الحضور والتقييمات
- واجهة عربية RTL وشعار الأكاديمية

## التشغيل على Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

افتح:
http://127.0.0.1:5000

## حساب الإدارة الافتراضي

- Email: admin@mawadda.local
- Password: Admin@123

غيّر كلمة المرور والـ SECRET_KEY قبل الاستخدام الفعلي.

## النشر على Render

ارفع الملفات إلى GitHub ثم:
- New Web Service
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`

> SQLite مناسبة للتجربة. عند التشغيل الحقيقي استخدم PostgreSQL.


## إضافات Phase 2

- عقود اشتراك مرنة بسعر مختلف لكل طالب
- دعم عملات متعددة: EGP / USD / SAR / AED / KWD / QAR / EUR / GBP
- عدد حصص ومدة حصة مختلفة لكل عقد
- خصم مستقل لكل عقد
- تحديد المعلم ومستحقه لكل حصة داخل العقد
- دفعات جزئية وسجل إيصالات
- عرض إجمالي العقد والمدفوع والمتبقي
- ولي الأمر يرى عقود ومدفوعات أبنائه فقط
- المعلم يرى العقود المسندة إليه
- تعطيل/تفعيل حساب المعلم أو ولي الأمر
- الحساب المعطل لا يستطيع تسجيل الدخول


## إضافات Phase 3

- خزائن متعددة وعملات متعددة
- رصيد افتتاحي ورصيد حالي لكل خزنة
- إيرادات ومصروفات وتصنيفات مالية
- ربط دفعات الاشتراكات بالخزنة
- استحقاق المعلم لكل حصة منفذة
- احتساب مختلف حسب عقد كل طالب
- كشوف مستحقات بفترة محددة
- مكافآت وخصومات وصافي مستحق
- دفع كشف المعلم وتسجيله كمصروف على الخزنة
- تقارير الإيرادات والمصروفات وصافي الحركة
- تقرير المبالغ المستحقة من أولياء الأمور
- تقرير مستحقات المعلمين غير المدفوعة
- بيانات اختبار كاملة

## إنشاء بيانات الاختبار

بعد تثبيت المتطلبات:

```powershell
flask --app app seed-test-data
python app.py
```

حسابات الاختبار:

- الإدارة: `admin@mawadda.local` / `Admin@123`
- المعلم: `teacher1@mawadda.local` / `Teacher@123`
- ولي الأمر: `parent1@mawadda.local` / `Parent@123`


## إضافات Phase 4

- موقع عام للأكاديمية على `/home`
- صفحة خدمات وفريق عمل ونموذج تواصل
- رسائل العملاء تظهر داخل لوحة الإدارة
- PWA قابلة للإضافة إلى شاشة الموبايل
- Service Worker وManifest
- مركز إشعارات داخل النظام
- عداد إشعارات غير مقروءة
- إشعار ولي الأمر عند إضافة تقييم جديد
- توليد إشعارات لقرب انتهاء الاشتراك والمبالغ المستحقة
- إشعار المعلم بحصص اليوم
- قوالب واتساب قابلة للتخصيص
- زر واتساب لتذكير ولي الأمر بالاشتراك
- زر واتساب لإرسال تقرير الحصة

## تجهيز Phase 4

```powershell
flask --app app seed-phase4
flask --app app generate-notifications
python app.py
```

## ملاحظة واتساب

النسخة الحالية تستخدم روابط WhatsApp Click-to-Chat، ولذلك لا تحتاج API أو بطاقة دفع.
الإرسال التلقائي بالكامل يحتاج Meta WhatsApp Cloud API وحساب Business موثق ورقم مخصص.


## التعديلات التشغيلية

1. كود الطالب تلقائي بدءًا من 100.
2. كود المعلم تلقائي بدءًا من 200.
3. إعادة جدولة الحصة.
4. حصة تعويضية.
5. مدة فعلية ونوع الحصة.
6. تجميد الاشتراك مع تمديد تاريخ النهاية.
7. سجل القرآن: السورة والآيات والحفظ والمراجعة والأخطاء.
8. صفحة مالية للمعلم تعرض المستحق والمدفوع والمتبقي.
9. تسجيل دفعات المعلمين بفترة الدفع وطريقة الدفع والمرجع.
10. خصم دفعة المعلم من الخزنة وتسجيل حركة مالية.

> ملاحظة: استحقاقات المعلمين مصممة بالجنيه المصري في دفعات المعلم. عقود الطلاب قد تظل بعملات مختلفة.


## الإضافات الجديدة

- المعلم يمكن أن يكون من أي جنسية، لكن التسوية المالية والدفعات بالجنيه المصري.
- عقد الطالب يمكن أن يكون بأي عملة.
- خياران لمستحق المعلم:
  - مبلغ ثابت بالجنيه.
  - قيمة بعملة العقد تُحوّل تلقائيًا إلى الجنيه بسعر محفوظ.
- شاشة أسعار العملات إلى EGP.
- أكواد تلقائية معبرة:
  - الطالب: `STU-0100`
  - المعلم: `TCH-0200`
  - ولي الأمر: `PAR-0300`
- شاشة إعدادات تغيّر Prefix والرقم القادم وعدد الخانات بدون تعديل الكود.
- ترقية SQLite تلقائيًا بدون حذف قاعدة البيانات.
- ولي الأمر يقدّم شكوى فقط ضد معلم يعمل مع أحد أبنائه.
- ولي الأمر يطلب تغيير المعلم فقط من المعلمين المرتبطين بأبنائه.
- الإدارة تراجع الشكوى وترد عليها.
- الإدارة توافق أو ترفض طلب تغيير المعلم.
- عند الموافقة، يتم تحديث الحلقة والعقد للمعلم الجديد تلقائيًا قدر الإمكان.

## Password reset email
Configure these environment variables to send password-reset links:
`SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` (1/0).
Reset links expire after 30 minutes and become invalid immediately after a password change.

## الأدوار الجديدة
- Developer: admin@mawadda.local / Admin@123
- Manager: manager@mawadda.local / Manager@123
- Accounting Manager: accounts@mawadda.local / Accounts@123

## Gmail
من داخل النظام: إعدادات Gmail. استخدم smtp.gmail.com والمنفذ 587 وTLS، مع App Password من Google بدل كلمة مرور Gmail الأساسية.

## Management accounts
- Developer: admin@mawadda.local / Admin@123
- Manager: manager@mawadda.local / Manager@123
- Accounting Manager: accounts@mawadda.local / Accounts@123

The Developer has unrestricted access. The Manager can edit any parent/teacher/user profile, upload a profile image, activate/deactivate the account, and optionally reset the password. Leaving the password field blank keeps the current password. Demo data can be removed from Users > Clear test data while preserving management accounts and system settings.

## Role matrix (fixed)
- Developer: full access and bypasses permission checks.
- Manager: academy operations, profiles, evaluations, reports; no permissions or Gmail settings.
- Accounting Manager: finance, contracts, reports, journal, and administrative profile screen only.
- Teacher: own students, sessions, evaluations, profile, and earnings only.
- Parent: own children, linked teachers/sessions/contracts, complaints, change requests, and profile only.

Legacy `admin` authorization checks were removed. Existing legacy users are migrated to `developer` at startup.

## Final user management update
- The `admin` role has unconditional access to all routes and permissions.
- The central Users & Profiles page manages admins, managers, accounting managers, teachers, parents, and students.
- Admin can edit any user's identity data, photo, active status, role, and optionally reset the password.
- Teacher and parent profile-specific data is edited in the same form.
- Student profile and photo are edited from the same central page through the student profile editor.
- Existing `developer` records are migrated automatically to `admin` for backward compatibility.
#   m a w a d d a - a c a d e m y  
 