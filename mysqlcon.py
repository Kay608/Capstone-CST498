
"mysql://pibeadwopo2puu2w:ia58h6oid99au8x4@d6vscs19jtah8iwb.cbetxkdyhwsb.us-east-1.rds.amazonaws.com:3306/cdzpl48ljf6v83hureconnect=true"
import mysql.connector 
connection = mysql.connector.connect(host='d6vscs19jtah8iwb.cbetxkdyhwsb.us-east-1.rds.amazonaws.com', 
database='cdzpl48ljf6v83hu', 
user='pibeadwopo2puu2w', 
password='ia58h6oid99au8x4')
if connection.is_connected()==0: 
    print("Connection failed.")
    # prints the exit message 
    print(exit) 
    exit() 
db_Info = connection.get_server_info() 
print("Connected to MySQL Server version ", db_Info) 
cursor = connection.cursor() 
my_table_name="employee" 
my_table_exist=0 
# showing databases 
print("\nshowing all the databases") 
sql_select_Query = "show databases;" 
cursor.execute(sql_select_Query) 
# getting all records 
records = cursor.fetchall() 
print(records) 
strformat="database {}: {}" 
for row in range(0,cursor.rowcount): 
    print(strformat.format(row,records[row])) 
# selecting the current database 
print("\nselect the current database") 
cursor.execute("select database();") 
record = cursor.fetchone() 
print("You're connected to database: ", record)     
# showing tables 
print("\nshowing tables from the selected database") 
sql_select_Query = "show tables;" 
cursor.execute(sql_select_Query)
records = cursor.fetchall() 
print(records) 
strformat="table {}: {}" 
for row in range(0,cursor.rowcount): 
    print(strformat.format(row,records[row])) 
str1=''.join(records[row]) 
if my_table_name == str1: 
    my_table_exist=1        
# creating tables 
if my_table_exist!=1: 
    print("\ncreating tables in the selected database") 
    sql_select_Query = "create table "+my_table_name+"(firstname varchar(20) not null, lastname varchar(20) not null, id int);" 
    cursor.execute(sql_select_Query)
# inserting tuples into table 
print("\ninserting tuples in the selected table") 
sql_select_Query = "insert into "+my_table_name+" values ('Wang1', 'Zhaohui', 9267879991);" 
cursor.execute(sql_select_Query) 
sql_select_Query = "insert into "+my_table_name+" values ('Wang2', 'Zhaohui', 9267879992);" 
cursor.execute(sql_select_Query) 
connection.commit()    
# showing content of table 
print("\nshowing the content of the selected table") 
sql_select_Query = "show columns from "+my_table_name 
cursor.execute(sql_select_Query) 
# get all records 
records = cursor.fetchall() 
print(records) 
table_field_num=cursor.rowcount 
strformat="Name: {}, Type: {}" 
table_field_format="" 
for row in records: 
    print(strformat.format(row[0], row[1])) 
table_field_format=table_field_format+row[0]+": {}," 
print(table_field_format)  
sql_select_Query = "select * from "+my_table_name 
cursor.execute(sql_select_Query) 
# get records 
records = cursor.fetchall() 
#print(records) 
print("Total number of rows in table: ", cursor.rowcount) 
for row in records:  # prints the exit message 
    if table_field_num == 1: 
        print(table_field_format.format(row[0])) 
    if table_field_num == 2: 
        print(table_field_format.format(row[0], row[1])) 
    if table_field_num == 3: 
        print(table_field_format.format(row[0], row[1], row[2])) 
    if table_field_num == 4: 
        print(table_field_format.format(row[0], row[1], row[2], row[3])) 
    if table_field_num == 5: 
        print(table_field_format.format(row[0], row[1], row[2], row[3], row[4])) 
    if table_field_num == 6: 
        print(table_field_format.format(row[0], row[1], row[2], row[3], row[4], row[5]))     
# disconnecting MySQL 
if connection.is_connected(): 
    cursor.close() 
connection.close() 
print("MySQL connection is closed") 