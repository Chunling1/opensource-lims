from pdf_helper import PdfMaker

"""
本函数功能描述如下：
1.本功能用于将用户上传的文件组合成最终的报告，输入文件只接收按顺序编排好的pdf文件。
2.模块根据初始化时提供的报告类型、语言以及版本，对上传的文件列表文件进行编排组合、添加背景、添加页码。
3.文件编排顺序如下：系统根据表单信息生成的报告、用户补充后的完整报告、用户额外附加的其他文件（仅接收docx以及pdf文件）
4.当用户直接采用系统生成的报告时，用户补充后的完整报告参数应使用空字符串
5.当直接采用用户补充的完整报告时，系统生成的报告参数应使用空字符串
6.本模块只接受pdf文件，系统需要将用户上传的所有非pdf文件转为pdf后，再按参数要求提供给本模块。
7.当用户附加的额外文件中包含Conclusion.docx文件时，系统应根据表单信息重新生成报告（需要将Conclusion字段指定为Conclusion.docx文件的路径，
  报告中的检测结论将会被替换为docx文件中的内容和格式），在转换为pdf后将路径提供给本模块参数1。
8.添加签发日期的功能，需要在电子签章发起前单独调用。
"""
if __name__ == '__main__':
    """
    Input files shall be arranged in the following order:
    1. System-generated files — required.
    2. User-uploaded files — required; leave blank if the user has not uploaded any files.
    3. Other user-uploaded files — optional.
    """
    pdf = PdfMaker('Engineering', 'CN', extended=False)
    # output = pdf.make(['output/entrust_sample.pdf', ''], 'output/entrust_compose.pdf')
    # print(output)
    # add issue date
    output = pdf.add_issue_date('report_sample.pdf', 'report_sample1.pdf')
    print(output)
