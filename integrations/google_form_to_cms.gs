/** Paste into Apps Script of the business registration Google Form.
 * Script properties:
 *   CMS_PULL_SECRET = same value as Flask's CMS_FORMS_PULL_SECRET (local Flask)
 * Optional push mode when Flask has a public HTTPS URL:
 *   CMS_API_URL and CMS_WEBHOOK_SECRET; then run installCmsTrigger() once.
 */

function installCmsTrigger() {
  const name = 'onBusinessFormSubmit';
  for (const trigger of ScriptApp.getProjectTriggers()) {
    if (trigger.getHandlerFunction() === name) ScriptApp.deleteTrigger(trigger);
  }
  ScriptApp.newTrigger(name).forForm(FormApp.getActiveForm()).onFormSubmit().create();
}

function onBusinessFormSubmit(event) {
  sendResponseToCms_(event.source, event.response);
}

// Run manually once if the Form already has submissions before the trigger was installed.
function importExistingResponses() {
  const form = FormApp.getActiveForm();
  for (const response of form.getResponses()) sendResponseToCms_(form, response);
}

function sendResponseToCms_(form, response) {
  const body = responsePayload_(form, response);
  const properties = PropertiesService.getScriptProperties();
  const url = properties.getProperty('CMS_API_URL');
  const secret = properties.getProperty('CMS_WEBHOOK_SECRET');
  if (!url || !secret) throw new Error('Missing CMS_API_URL or CMS_WEBHOOK_SECRET script property');
  const result = UrlFetchApp.fetch(url, {
    method: 'post', contentType: 'application/json',
    headers: { 'X-CMS-Webhook-Secret': secret },
    payload: JSON.stringify(body), muteHttpExceptions: true,
  });
  if (result.getResponseCode() < 200 || result.getResponseCode() >= 300) {
    throw new Error(`CMS intake failed: ${result.getResponseCode()} ${result.getContentText()}`);
  }
}

// Deploy this script as a Web App when Flask is local. CMS calls doPost to pull responses.
function doPost(event) {
  const input = JSON.parse(event.postData.contents || '{}');
  const expected = PropertiesService.getScriptProperties().getProperty('CMS_PULL_SECRET');
  if (!expected || input.secret !== expected) return json_({ error: 'unauthorized' });
  const form = FormApp.getActiveForm();
  const responses = form.getResponses();
  const offset = Math.max(0, Math.min(100000, Number(input.offset) || 0));
  const limit = Math.max(1, Math.min(100, Number(input.limit) || 100));
  return json_({ total: responses.length, items: responses.slice(offset, offset + limit).map(response => responsePayload_(form, response)) });
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

function responsePayload_(form, response) {
  const answers = {};
  for (const entry of response.getItemResponses()) {
    const title = entry.getItem().getTitle().trim();
    const value = entry.getResponse();
    answers[title] = entry.getItem().getType().toString() === 'FILE_UPLOAD'
      ? (value || []).map(id => `https://drive.google.com/file/d/${id}/view`)
      : value;
  }
  const files = answers['Hồ sơ kinh doanh'] || [];
  return {
    source_id: `google-form:${form.getId()}:${response.getId()}`,
    submitted_at: Math.floor(response.getTimestamp().getTime() / 1000),
    answers,
    email: answers['Email'] || response.getRespondentEmail() || '',
    owner_name: answers['Tên chủ kinh doanh'] || '',
    business_name: answers['Tên công ti, quán, doanh nghiệp'] || '',
    tax_id: answers['Mã số thuế'] || '',
    license_file: files[0] || '',
    ward: answers['Phường'] || '',
    address: answers['Nhập địa chỉ Chi tiết'] || '',
    phone: answers['Số điện thoại'] || '',
  };
}
